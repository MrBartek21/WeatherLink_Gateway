import threading
import time
import socket
import os

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
        self.screen_awake_since = time.monotonic()
        self.screen_wake_at = None
        self.display_sleeping = False
        self.cpu_previous = None
        self.cpu_cached = 0.0
        self.cpu_sample_time = 0.0

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
            self.screen_awake_since = time.monotonic()
            self.screen_wake_at = None
            self.display_sleeping = False

            self._draw_splash()

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
                    else:
                        self._tick_screen_saver()

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
            10,
            bold=True
        )

        normal_font = self._font(
            9,
            bold=False
        )

        small_font = self._font(
            8,
            bold=False
        )

        y = 0

        for index, line in enumerate(lines):

            if index == 0:
                font = title_font
                step = 11

            elif index >= 5:
                font = small_font
                step = 9

            else:
                font = normal_font
                step = 10

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

    def _draw_splash(self):
        if not self.available:
            return

        width, height = self.device.width, self.device.height
        image = Image.new("1", (width, height), 0)
        draw = ImageDraw.Draw(image)
        large = self._font(13, bold=True)
        medium = self._font(10, bold=True)
        small = self._font(8)

        # Prosta ikona słońca nad horyzontem.
        draw.ellipse((10, 10, 30, 30), outline=255, width=2)
        draw.line((20, 5, 20, 9), fill=255, width=2)
        draw.line((20, 31, 20, 35), fill=255, width=2)
        draw.line((5, 20, 9, 20), fill=255, width=2)
        draw.line((31, 20, 35, 20), fill=255, width=2)
        draw.arc((0, 24, 40, 48), 200, 340, fill=255, width=2)

        draw.text((43, 7), "WEATHERLINK", fill=255, font=medium)
        draw.text((43, 22), "GATEWAY", fill=255, font=large)
        draw.line((8, 43, width - 8, 43), fill=255)
        draw.text((15, 49), "URUCHAMIANIE STACJI...", fill=255, font=small)
        self.device.display(image)

    def _draw_system_dashboard(self):
        if not self.available:
            return

        width = self.device.width
        height = self.device.height
        image = Image.new("1", (width, height), 0)
        draw = ImageDraw.Draw(image)
        title_font = self._font(10, bold=True)
        label_font = self._font(8, bold=True)
        value_font = self._font(15, bold=True)
        small_font = self._font(7, bold=False)

        draw.text((3, 0), "WEATHERLINK", fill=255, font=title_font)
        draw.text((width - 38, 2), "SYSTEM", fill=255, font=small_font)
        draw.line((3, 13, width - 4, 13), fill=255)

        ids = ", ".join(sorted(self.node_packets.keys(), key=int)) or "—"
        draw.text((3, 16), "NODY", fill=255, font=label_font)
        draw.text((34, 16), ids[:20], fill=255, font=small_font)

        cpu = self.get_cpu_usage()
        ram = self.get_ram_usage()
        col_width = (width - 12) // 2
        right_x = 6 + col_width

        draw.text((3, 27), "CPU", fill=255, font=label_font)
        draw.text((right_x, 27), "RAM", fill=255, font=label_font)
        draw.text((3, 34), f"{cpu:.0f}%", fill=255, font=value_font)
        draw.text((right_x, 34), f"{ram:.0f}%", fill=255, font=value_font)

        bar_y = 52
        bar_width = col_width - 5
        for x, percent in ((3, cpu), (right_x, ram)):
            draw.rectangle((x, bar_y, x + bar_width, bar_y + 4), outline=255)
            fill_width = int((bar_width - 2) * max(0, min(100, percent)) / 100)
            if fill_width:
                draw.rectangle((x + 1, bar_y + 1, x + fill_width, bar_y + 3), fill=255)

        uptime = f"UP  {self.get_uptime()}"[:20]
        draw.text((3, 58), uptime, fill=255, font=small_font)
        self.device.display(image)

    def _draw_node_dashboard(self, node_id, packet, screen):
        if not self.available:
            return

        width = self.device.width
        height = self.device.height
        image = Image.new("1", (width, height), 0)
        draw = ImageDraw.Draw(image)
        title_font = self._font(10, bold=True)
        label_font = self._font(8, bold=True)
        value_font = self._font(14, bold=True)
        small_font = self._font(8, bold=False)
        status = int(packet.get("status", 0))

        if screen == "weather":
            draw.rectangle((0, 0, width - 1, 12), fill=255)
            draw.text((4, 1), "POGODA", fill=0, font=title_font)
            draw.text((width - 52, 2), f"NODE {node_id}", fill=0, font=small_font)

            draw.text((4, 16), "TEMP AHT20", fill=255, font=label_font)
            draw.text((4, 25), f"{packet.get('aht_temperature', 0):.1f} C" if status & 0x01 else "--.- C", fill=255, font=value_font)
            draw.text((70, 16), "WILGOTNOSC", fill=255, font=label_font)
            draw.text((70, 25), f"{packet.get('aht_humidity', 0):.0f} %" if status & 0x01 else "-- %", fill=255, font=value_font)
            draw.line((64, 16, 64, 41), fill=255)
            draw.line((3, 43, width - 4, 43), fill=255)

            draw.text((4, 46), "BMP hPa", fill=255, font=label_font)
            draw.text((4, 55), f"{packet.get('bmp_pressure', 0) / 100:.0f}" if status & 0x02 else "---", fill=255, font=small_font)
            draw.line((43, 46, 43, 63), fill=255)
            draw.text((49, 46), "DS18 C", fill=255, font=label_font)
            draw.text((49, 55), f"{packet.get('ds_temperature', 0):.1f}" if status & 0x04 else "--.-", fill=255, font=small_font)
            draw.line((91, 46, 91, 63), fill=255)
            draw.text((97, 46), "LIGHT", fill=255, font=label_font)
            draw.text((97, 55), str(packet.get("light", "--")) if status & 0x08 else "---", fill=255, font=small_font)
        else:
            draw.rectangle((0, 0, width - 1, 12), fill=255)
            draw.text((4, 1), "ZASILANIE", fill=0, font=title_font)
            draw.text((width - 52, 2), f"NODE {node_id}", fill=0, font=small_font)

            has_ina = bool(status & 0x10)
            voltage = packet.get("ina1_voltage", 0) if has_ina else 0
            percent = self.battery_percent(voltage) if has_ina else 0
            draw.text((4, 16), f"{percent:3d}%" if has_ina else " --%", fill=255, font=value_font)
            draw.text((60, 19), "BATERIA", fill=255, font=label_font)
            draw.text((60, 29), f"{voltage:.2f} V" if has_ina else "BRAK DANYCH", fill=255, font=small_font)
            draw.rectangle((3, 36, 53, 44), outline=255)
            draw.text((7, 37), f"SEQ {packet.get('sequence', '-')}", fill=255, font=self._font(7, bold=True))

            draw.line((3, 46, width - 4, 46), fill=255)
            draw.text((3, 47), "CH1 A", fill=255, font=label_font)
            draw.text((45, 47), "CH2 V/A", fill=255, font=label_font)
            draw.text((91, 47), "CH3 V/A", fill=255, font=label_font)
            if has_ina:
                draw.text((3, 55), f"{packet.get('ina1_current', 0):.2f}", fill=255, font=self._font(7))
                draw.text((45, 55), f"{packet.get('ina2_voltage', 0):.1f}/{packet.get('ina2_current', 0):.2f}", fill=255, font=self._font(7))
                draw.text((91, 55), f"{packet.get('ina3_voltage', 0):.1f}/{packet.get('ina3_current', 0):.2f}", fill=255, font=self._font(7))
            else:
                draw.text((3, 55), "--", fill=255, font=self._font(7))
                draw.text((45, 55), "--", fill=255, font=self._font(7))
                draw.text((91, 55), "--", fill=255, font=self._font(7))

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
            else:
                weather.append("DS --.- C")
            if status & 0x08:
                weather.append(f"LIGHT {p.get('light', 0)}")
            pages.append(weather)

            energy = [f"ZASILANIE NODE {node_id}"]
            if status & 0x10:
                voltage = p.get("ina1_voltage", 0)
                energy.append(f"Bateria {voltage:.2f}V {self.battery_percent(voltage)}%")
                energy.append(f"CH1 {p.get('ina1_current', 0):.2f} A")
                energy.append(f"CH2 {p.get('ina2_voltage', 0):.2f}V {p.get('ina2_current', 0):.2f}A")
                energy.append(f"CH3 {p.get('ina3_voltage', 0):.2f}V {p.get('ina3_current', 0):.2f}A")
            else:
                energy += ["Bateria --.-V --%", "CH1 --", "CH2 --", "CH3 --"]
            energy.append(f"SEQ {p.get('sequence', '-')}")
            pages.append(energy)

        ids = ", ".join(sorted(self.node_packets.keys(), key=int))
        pages.append([
            "SYSTEM GATEWAY",
            f"NODY: {ids}"[:22],
            f"UP {self.get_uptime()}",
            f"CPU {self.get_cpu_usage():.0f}%",
            f"RAM {self.get_ram_usage():.0f}%"
        ])

        return pages

    def get_cpu_usage(self):
        now = time.monotonic()
        if now - self.cpu_sample_time < 1.0:
            return self.cpu_cached
        try:
            with open("/proc/stat", "r", encoding="ascii") as f:
                fields = f.readline().split()[1:]
            values = [int(value) for value in fields]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            total = sum(values)
            previous = self.cpu_previous
            self.cpu_previous = (idle, total)
            self.cpu_sample_time = now
            if previous is None:
                self.cpu_cached = 0.0
                return self.cpu_cached
            idle_delta = idle - previous[0]
            total_delta = total - previous[1]
            self.cpu_cached = 0.0 if total_delta <= 0 else max(0.0, min(100.0, 100.0 * (1 - idle_delta / total_delta)))
            return self.cpu_cached
        except (OSError, ValueError, IndexError):
            return self.cpu_cached

    @staticmethod
    def get_ram_usage():
        try:
            values = {}
            with open("/proc/meminfo", "r", encoding="ascii") as f:
                for line in f:
                    key, value = line.split(":", 1)
                    if key in ("MemTotal", "MemAvailable"):
                        values[key] = int(value.strip().split()[0])
            total = values["MemTotal"]
            available = values["MemAvailable"]
            return 0.0 if total <= 0 else 100.0 * (total - available) / total
        except (OSError, ValueError, KeyError, IndexError):
            return 0.0

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

        if not self._tick_screen_saver():
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

        if self.page == len(pages) - 1:
            self._draw_system_dashboard()
        else:
            nodes = sorted(self.node_packets.items(), key=lambda item: int(item[0]))
            node_index = self.page // 2
            node_id, packet = nodes[node_index]
            screen = "weather" if self.page % 2 == 0 else "power"
            self._draw_node_dashboard(node_id, packet, screen)

    def _tick_screen_saver(self):
        if not self.available:
            return False

        enabled = bool(self.config.get("oled.screen_saver_enabled", True))
        if not enabled:
            if self.display_sleeping:
                self.device.show()
                self.display_sleeping = False
            self.screen_awake_since = time.monotonic()
            self.screen_wake_at = None
            return True

        now = time.monotonic()
        if self.display_sleeping:
            if self.screen_wake_at is not None and now < self.screen_wake_at:
                return False
            self.device.show()
            self.display_sleeping = False
            self.screen_awake_since = now
            self.screen_wake_at = None
            return True

        on_seconds = max(1, self.config.get_int("oled.screen_on_seconds", 300))
        if now - self.screen_awake_since >= on_seconds:
            self.device.hide()
            self.display_sleeping = True
            off_seconds = max(1, self.config.get_int("oled.screen_off_seconds", 60))
            self.screen_wake_at = now + off_seconds
            return False
        return True

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

            "sleeping": self.display_sleeping,

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
