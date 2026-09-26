import threading
import time
import socket

try:
    from PIL import Image, ImageDraw, ImageFont
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
except ImportError:
    Image = ImageDraw = ImageFont = i2c = ssd1306 = None


class OLEDDisplay:

    def __init__(self, config):
        self.config = config

        self.device = None
        self.available = False

        self.node_packets = {}
        self.last_packet = None

        self.page = 0
        self.last_page = time.monotonic()

        self.start_time = time.monotonic()

        self.lock = threading.Lock()

        self.running = False
        self.thread = None

        self.apply_config()

    # =========================================================
    # OLED INIT
    # =========================================================

    def apply_config(self):
        self.stop()

        if not self.config.get("oled.enabled", True):
            return

        if ssd1306 is None:
            print("[OLED] Brak bibliotek PIL/luma")
            return

        try:
            bus = self.config.get_int(
                "oled.i2c_bus",
                1
            )

            address = int(
                str(
                    self.config.get(
                        "oled.address",
                        "0x3C"
                    )
                ),
                0
            )

            serial = i2c(
                port=bus,
                address=address
            )

            self.device = ssd1306(
                serial,
                width=self.config.get_int(
                    "oled.width",
                    128
                ),
                height=self.config.get_int(
                    "oled.height",
                    64
                ),
                rotate=self.config.get_int(
                    "oled.rotation",
                    0
                )
            )

            self.available = True

            self._draw([
                "WeatherLink",
                "Gateway",
                "",
                "OLED OK"
            ])

            self.running = True

            self.thread = threading.Thread(
                target=self._display_loop,
                daemon=True
            )

            self.thread.start()

            print("[OLED] Uruchomiony")

        except Exception as exc:
            self.available = False
            self.device = None

            print("[OLED] Błąd:", exc)

    # =========================================================
    # DISPLAY LOOP
    # =========================================================

    def _display_loop(self):

        while self.running:

            try:
                with self.lock:

                    if self.last_packet:
                        self.render()

                time.sleep(0.2)

            except Exception as exc:
                print("[OLED] Render error:", exc)
                time.sleep(1)

    # =========================================================
    # FONTS
    # =========================================================

    def _font(self, size=11, bold=False):

        paths = []

        if bold:
            paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            ]
        else:
            paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            ]

        for path in paths:

            try:
                return ImageFont.truetype(
                    path,
                    size
                )
            except Exception:
                pass

        return ImageFont.load_default()

    # =========================================================
    # DRAW
    # =========================================================

    def _draw(self, lines):

        if not self.available:
            return

        image = Image.new(
            "1",
            (
                self.device.width,
                self.device.height
            ),
            0
        )

        draw = ImageDraw.Draw(image)

        # Większa i czytelniejsza czcionka
        title_font = self._font(
            11,
            bold=True
        )

        normal_font = self._font(
            10,
            bold=False
        )

        small_font = self._font(
            9,
            bold=False
        )

        y = 0

        for index, line in enumerate(lines):

            if index == 0:
                font = title_font
                step = 12

            elif index >= 5:
                font = small_font
                step = 10

            else:
                font = normal_font
                step = 11

            text = str(line)

            # OLED 128 px – ograniczenie długości
            # zależne od czcionki.
            draw.text(
                (0, y),
                text[:22],
                fill=255,
                font=font
            )

            y += step

            if y >= self.device.height:
                break

        self.device.display(image)

    # =========================================================
    # IP
    # =========================================================

    def get_ip(self):

        try:
            s = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
            )

            s.settimeout(1)

            # Nie wysyłamy żadnych danych.
            # Połączenie służy tylko do ustalenia
            # lokalnego adresu interfejsu.
            s.connect(
                ("8.8.8.8", 80)
            )

            ip = s.getsockname()[0]

            s.close()

            return ip

        except Exception:
            return "N/A"

    # =========================================================
    # UPTIME
    # =========================================================

    def get_uptime(self):

        seconds = int(
            time.monotonic() - self.start_time
        )

        days = seconds // 86400
        seconds %= 86400

        hours = seconds // 3600
        seconds %= 3600

        minutes = seconds // 60
        seconds %= 60

        if days > 0:
            return (
                f"{days}d "
                f"{hours:02d}h "
                f"{minutes:02d}m"
            )

        if hours > 0:
            return (
                f"{hours:02d}h "
                f"{minutes:02d}m "
                f"{seconds:02d}s"
            )

        return (
            f"{minutes:02d}m "
            f"{seconds:02d}s"
        )

    # =========================================================
    # PACKET
    # =========================================================

    def update(self, packet):

        with self.lock:
            self.last_packet = packet
            node_id = str(packet.get("node_id", 0))
            self.node_packets[node_id] = packet

    def update_nodes(self, packets):
        with self.lock:
            self.node_packets = {str(k): dict(v) for k, v in packets.items()}
            if self.node_packets:
                latest = max(self.node_packets.values(), key=lambda p: p.get("received_at", 0))
                self.last_packet = latest

    # =========================================================
    # BUILD PAGES
    # =========================================================

    def _build_pages(self):

        if not self.node_packets:
            return [
                [
                    "WeatherLink",
                    "Gateway",
                    "",
                    "Brak danych"
                ]
            ]

        pages = []
        for node_id, p in sorted(self.node_packets.items(), key=lambda item: int(item[0])):
            status = int(p.get("status", 0))
            weather = [f"POGODA  NODE {node_id}"]
            if status & 0x01:
                weather += [f"T  {p.get('aht_temperature', 0):.1f} C",
                            f"RH {p.get('aht_humidity', 0):.1f} %"]
            if status & 0x02:
                weather.append(f"P  {p.get('bmp_pressure', 0) / 100:.1f} hPa")
            if status & 0x04:
                weather.append(f"DS {p.get('ds_temperature', 0):.1f} C")
            if status & 0x08:
                weather.append(f"LIGHT {p.get('light', 0)}")
            if len(weather) > 1:
                pages.append(weather)

            energy = [f"ZASILANIE NODE {node_id}"]
            if status & 0x10:
                voltage = p.get("ina1_voltage", 0)
                energy.append(f"Bateria {voltage:.2f}V {self.battery_percent(voltage)}%")
                energy.append(f"CH1 {p.get('ina1_current', 0):.2f} A")
                energy.append(f"CH2 {p.get('ina2_voltage', 0):.2f}V {p.get('ina2_current', 0):.2f}A")
                energy.append(f"CH3 {p.get('ina3_voltage', 0):.2f}V {p.get('ina3_current', 0):.2f}A")
            if len(energy) > 1:
                pages.append(energy)

            pages.append([
                f"SYSTEM  NODE {node_id}",
                f"IP {self.get_ip()}",
                f"UP {self.get_uptime()}",
                f"SEQ {p.get('sequence', '-')}",
                "NRF  CRC OK"
            ])

        return pages

    @staticmethod
    def battery_percent(voltage):
        # Przybliżona krzywa spoczynkowa dla typowego pakietu Li-ion/LiPo 1S.
        curve = [(3.00, 0), (3.30, 5), (3.50, 10), (3.60, 20),
                 (3.70, 40), (3.80, 60), (3.90, 75), (4.00, 85),
                 (4.10, 95), (4.20, 100)]
        if voltage <= curve[0][0]:
            return 0
        if voltage >= curve[-1][0]:
            return 100
        for (v0, p0), (v1, p1) in zip(curve, curve[1:]):
            if voltage <= v1:
                return round(p0 + (voltage - v0) * (p1 - p0) / (v1 - v0))

    # =========================================================
    # RENDER
    # =========================================================

    def render(self):

        if not self.available:
            return

        pages = self._build_pages()

        if not pages:
            return

        # Jeżeli liczba stron się zmieniła
        # zabezpieczamy indeks.
        if self.page >= len(pages):
            self.page = 0

        seconds = self.config.get_int(
            "oled.page_seconds",
            5
        )

        now = time.monotonic()

        if (
            now - self.last_page
            >= seconds
        ):

            self.page += 1

            if self.page >= len(pages):
                self.page = 0

            self.last_page = now

        self._draw(
            pages[self.page]
        )

    # =========================================================
    # TEST
    # =========================================================

    def test(self):

        if not self.available:
            return False, "OLED niedostępny"

        try:

            self._draw([
                "WeatherLink",
                "OLED TEST",
                "",
                f"IP {self.get_ip()}",
                f"UP {self.get_uptime()}"
            ])

            return True, "Test OLED wykonany"

        except Exception as exc:

            return False, str(exc)

    # =========================================================
    # STATUS
    # =========================================================

    def status(self):

        return {
            "enabled": bool(
                self.config.get(
                    "oled.enabled",
                    True
                )
            ),

            "available": bool(
                self.available
            ),

            "last_sequence":
                self.last_packet.get(
                    "sequence"
                )
                if self.last_packet
                else None,

            "page":
                self.page,

            "ip":
                self.get_ip(),

            "uptime":
                self.get_uptime(),

            "status":
                self.last_packet.get(
                    "status"
                )
                if self.last_packet
                else None
        }

    # =========================================================
    # STOP
    # =========================================================

    def stop(self):

        self.running = False

        if (
            self.thread
            and self.thread.is_alive()
        ):

            self.thread.join(
                timeout=1
            )

        self.thread = None

        if self.device:

            try:
                self.device.clear()
            except Exception:
                pass

        self.device = None
        self.available = False
