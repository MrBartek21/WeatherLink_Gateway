import json
import threading
import time

try:
    import paho.mqtt.client as mqtt_client
except ImportError:
    mqtt_client = None

class MQTTManager:
    def __init__(self, config):
        self.config = config
        self.client = None
        self.connected = False
        self.last_error = None
        self.lock = threading.Lock()
        self.apply_config()

    def apply_config(self):
        if mqtt_client is None:
            self.last_error = "Brak biblioteki paho-mqtt"
            return
        self.stop()
        if not self.config.get("mqtt.enabled", False):
            return
        try:
            self.client = mqtt_client.Client(
                mqtt_client.CallbackAPIVersion.VERSION2,
                client_id=self.config.get("mqtt.client_id", "weatherlink-gateway")
            )
        except AttributeError:
            self.client = mqtt_client.Client(
                client_id=self.config.get("mqtt.client_id", "weatherlink-gateway")
            )

        username = self.config.get("mqtt.username", "")
        password = self.config.get("mqtt.password", "")
        if username:
            self.client.username_pw_set(username, password)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

        try:
            self.client.connect(
                self.config.get("mqtt.host", "127.0.0.1"),
                self.config.get_int("mqtt.port", 1883),
                60
            )
            self.client.loop_start()
        except Exception as exc:
            self.last_error = str(exc)
            self.connected = False

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        try:
            rc = int(reason_code)
        except Exception:
            rc = 0 if str(reason_code).lower() in ("success", "0") else -1
        self.connected = rc == 0
        if not self.connected:
            self.last_error = f"MQTT connect rc={reason_code}"

    def _on_disconnect(self, client, userdata, disconnect_flags=None, reason_code=None, properties=None):
        self.connected = False

    def _on_publish(self, *args, **kwargs):
        pass

    def loop(self):
        pass

    def stop(self):
        if self.client:
            try:
                self.client.loop_stop()
            except Exception:
                pass
            try:
                self.client.disconnect()
            except Exception:
                pass
        self.client = None
        self.connected = False

    def _topic(self, suffix):
        return f"{self.config.get('mqtt.base_topic', 'WeatherLink').strip('/')}/{suffix}"

    def publish(self, suffix, value):
        if not self.config.get("mqtt.enabled", False) or not self.client or not self.connected:
            return False
        try:
            payload = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            info = self.client.publish(
                self._topic(suffix),
                payload,
                qos=self.config.get_int("mqtt.qos", 1),
                retain=bool(self.config.get("mqtt.retain", True))
            )
            return info.rc == 0
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def publish_packet(self, data):
        if not data:
            return
        node_id = data.get("node_id", 0)
        prefix = f"node/{node_id}/"
        self.publish(prefix + "data", data)
        self.publish("data", data)  # zachowuje dotychczasowy topic z ostatnim pakietem
        if data.get("status", 0) & 0x01:
            self.publish(prefix + "aht20/temperature", data["aht_temperature"])
            self.publish(prefix + "aht20/humidity", data["aht_humidity"])
        if data.get("status", 0) & 0x02:
            self.publish(prefix + "bmp280/temperature", data["bmp_temperature"])
            self.publish(prefix + "bmp280/pressure", data["bmp_pressure"])
        if data.get("status", 0) & 0x04:
            self.publish(prefix + "ds18b20/temperature", data["ds_temperature"])
        if data.get("status", 0) & 0x08:
            self.publish(prefix + "temt6000/adc", data["light"])
        if data.get("status", 0) & 0x10:
            for i in (1, 2, 3):
                self.publish(prefix + f"ina3221/ch{i}/voltage", data[f"ina{i}_voltage"])
                self.publish(prefix + f"ina3221/ch{i}/current", data[f"ina{i}_current"])

        self.publish(prefix + "status", {
            "node_id": node_id,
            "sequence": data.get("sequence"),
            "sensor_status": data.get("status"),
            "gateway_time": time.time()
        })

    def test_publish(self):
        if not self.config.get("mqtt.enabled", False):
            return False, "MQTT jest wyłączone"
        if not self.connected:
            return False, self.last_error or "Brak połączenia z brokerem"
        ok = self.publish("test", {"gateway": "WeatherLink Gateway", "test": True, "time": time.time()})
        return (ok, "Test MQTT wysłany" if ok else "Nie udało się wysłać testu")

    def status(self):
        return {
            "enabled": bool(self.config.get("mqtt.enabled", False)),
            "connected": bool(self.connected),
            "host": self.config.get("mqtt.host", ""),
            "port": self.config.get_int("mqtt.port", 1883),
            "base_topic": self.config.get("mqtt.base_topic", "WeatherLink"),
            "last_error": self.last_error
        }
