import struct
from RF24 import RF24, RF24_PA_MIN, RF24_PA_LOW, RF24_PA_HIGH, RF24_PA_MAX, RF24_250KBPS

WEATHER_HEADER = 0xA5
WEATHER_VERSION = 1
PACKET_SIZE = 32

STATUS_AHT20 = 0x01
STATUS_BMP280 = 0x02
STATUS_DS18B20 = 0x04
STATUS_TEMT6000 = 0x08
STATUS_INA3221 = 0x10

PACKET_FORMAT = "<BBB hH hI h H Hh Hh Hh BBB"
if struct.calcsize(PACKET_FORMAT) != PACKET_SIZE:
    raise RuntimeError("Błąd rozmiaru WeatherPacket")

def weather_crc(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc

class NRFReceiver:
    def __init__(self, ce_pin=22, csn_pin=1, channel=50, address=b"WTHLS",
                 power=2, data_rate=0, payload_size=32, auto_ack=True,
                 retry_delay=5, retry_count=15):
        self.available = False
        self.init_error = None
        # Sequence counters are independent for every transmitter (Node ID).
        self.node_sequences = {}
        self.node_stats = {}
        self.packet_count = 0
        self.lost_packets = 0
        self.crc_errors = 0
        self.packet_errors = 0
        self.channel = channel
        self.address = address
        self.power = power
        self.payload_size = payload_size
        try:
            self.radio = RF24(ce_pin, csn_pin)
            if not self.radio.begin():
                raise RuntimeError("nRF24L01 nie odpowiada")
            self.radio.setAutoAck(auto_ack)
            self.radio.setRetries(retry_delay, retry_count)
            self.radio.setChannel(channel)
            self.radio.setDataRate(RF24_250KBPS)
            self.radio.setPALevel(self._power_const(power))
            try:
                self.radio.disableDynamicPayloads()
            except Exception:
                pass
            self.radio.setPayloadSize(payload_size)
            self.radio.openReadingPipe(1, address)
            self.radio.startListening()
            try:
                if not self.radio.isChipConnected():
                    raise RuntimeError("nRF24L01 nie odpowiada")
            except AttributeError:
                pass
            self.available = True
            print(f"[NRF] READY | {address.decode(errors='replace')} | CH {channel} | 250 KBPS | {payload_size} B")
        except Exception as exc:
            self.init_error = str(exc)
            print("[NRF] Błąd inicjalizacji:", exc)

    def _power_const(self, level):
        return {0: RF24_PA_MIN, 1: RF24_PA_LOW, 2: RF24_PA_HIGH}.get(level, RF24_PA_MAX)

    def check_crc(self, payload):
        return len(payload) == PACKET_SIZE and payload[-1] == weather_crc(payload[:-1])

    def decode_packet(self, payload):
        if len(payload) != PACKET_SIZE:
            self.packet_errors += 1
            return None
        if not self.check_crc(payload):
            self.crc_errors += 1
            return None
        try:
            values = struct.unpack(PACKET_FORMAT, payload)
        except struct.error:
            self.packet_errors += 1
            return None

        (header, version, sequence, aht_temp, aht_humidity, bmp_temp, bmp_pressure,
         ds_temp, light, v1, c1, v2, c2, v3, c3, status, reserved, crc) = values

        if header != WEATHER_HEADER or version != WEATHER_VERSION:
            self.packet_errors += 1
            return None

        node_id = reserved
        last_sequence = self.node_sequences.get(node_id)
        if last_sequence is not None:
            expected = (last_sequence + 1) & 0xFF
            if sequence != expected:
                lost = (sequence - expected) & 0xFF
                self.lost_packets += lost
                self.node_stats.setdefault(node_id, {"packets": 0, "lost": 0})["lost"] += lost
        self.node_sequences[node_id] = sequence
        stats = self.node_stats.setdefault(node_id, {"packets": 0, "lost": 0})
        stats["packets"] += 1
        self.packet_count += 1

        return {
            "sequence": sequence,
            "node_id": node_id,
            "aht_temperature": aht_temp / 100.0,
            "aht_humidity": aht_humidity / 100.0,
            "bmp_temperature": bmp_temp / 100.0,
            "bmp_pressure": bmp_pressure,
            "ds_temperature": ds_temp / 100.0,
            "light": light,
            "ina1_voltage": v1 / 1000.0,
            "ina1_current": c1 / 1000.0,
            "ina2_voltage": v2 / 1000.0,
            "ina2_current": c2 / 1000.0,
            "ina3_voltage": v3 / 1000.0,
            "ina3_current": c3 / 1000.0,
            "status": status,
            "crc": crc
        }

    def receive_packet(self):
        if not self.available or not self.radio.available():
            return None
        try:
            payload = self.radio.read(self.payload_size)
            return self.decode_packet(payload)
        except Exception as exc:
            self.packet_errors += 1
            print("[NRF] Błąd odbioru:", exc)
            return None

    def packet_to_text(self, data):
        if not data:
            return ""
        lines = []
        status = data["status"]
        if status & STATUS_AHT20:
            lines += ["[AHT20]",
                      f"TEMPERATURE: {data['aht_temperature']:.2f} C",
                      f"HUMIDITY: {data['aht_humidity']:.2f} %"]
        if status & STATUS_BMP280:
            lines += ["[BMP280]",
                      f"TEMPERATURE: {data['bmp_temperature']:.2f} C",
                      f"PRESSURE: {data['bmp_pressure']} Pa"]
        if status & STATUS_DS18B20:
            lines += ["[DS18B20]", f"DS18B20: {data['ds_temperature']:.2f} C"]
        if status & STATUS_TEMT6000:
            lines += ["[TEMT6000]", f"ADC: {data['light']}"]
        if status & STATUS_INA3221:
            lines += ["[INA3221]",
                      f"CH1: {data['ina1_voltage']:.2f} V / {data['ina1_current']:.3f} A",
                      f"CH2: {data['ina2_voltage']:.2f} V / {data['ina2_current']:.3f} A",
                      f"CH3: {data['ina3_voltage']:.2f} V / {data['ina3_current']:.3f} A"]
        return "\n".join(lines)

    def get_stats(self):
        return {
            "packets": self.packet_count,
            "lost": self.lost_packets,
            "crc_errors": self.crc_errors,
            "packet_errors": self.packet_errors,
            "last_sequence": None,
            "nodes": {str(node_id): {**stats, "last_sequence": self.node_sequences.get(node_id)}
                      for node_id, stats in self.node_stats.items()}
        }

    def close(self):
        try:
            self.radio.stopListening()
        except Exception:
            pass
