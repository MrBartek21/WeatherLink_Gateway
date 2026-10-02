"""Desktop preview for the WeatherLink Gateway's 128x64 OLED screens."""

import tkinter as tk
from pathlib import Path
import sys
from tkinter import ttk

from PIL import Image, ImageTk

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from oled_display import OLEDDisplay


class PreviewDevice:
    width = 128
    height = 64

    def __init__(self, on_frame):
        self.on_frame = on_frame

    def display(self, image):
        self.on_frame(image)


class PreviewOLED(OLEDDisplay):
    def get_cpu_usage(self):
        return self.preview_cpu

    def get_ram_usage(self):
        return self.preview_ram

    def get_uptime(self):
        return "01:23:45"


class OLEDEmulator:
    SCALE = 5

    def __init__(self, root):
        self.root = root
        root.title("WeatherLink Gateway — emulator OLED 128×64")
        root.resizable(False, False)

        self.screen_name = tk.StringVar(value="Pogoda")
        self.node_id = tk.StringVar(value="1")
        self.temperature = tk.DoubleVar(value=21.5)
        self.humidity = tk.DoubleVar(value=54)
        self.voltage = tk.DoubleVar(value=3.85)
        self.cpu = tk.DoubleVar(value=18)
        self.ram = tk.DoubleVar(value=42)

        self.canvas = tk.Canvas(
            root,
            width=128 * self.SCALE,
            height=64 * self.SCALE,
            background="#020605",
            highlightthickness=1,
            highlightbackground="#61736d",
        )
        self.canvas.grid(row=0, column=0, padx=16, pady=16, sticky="n")

        controls = ttk.Frame(root, padding=(0, 16, 16, 16))
        controls.grid(row=0, column=1, sticky="nsew")
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Podgląd ekranu", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        ttk.Label(controls, text="Widok").grid(row=1, column=0, sticky="w", padx=(0, 10))
        screen_picker = ttk.Combobox(
            controls,
            textvariable=self.screen_name,
            values=("Pogoda", "Zasilanie", "System", "Ekran startowy"),
            state="readonly",
            width=19,
        )
        screen_picker.grid(row=1, column=1, sticky="ew", pady=3)
        screen_picker.bind("<<ComboboxSelected>>", self.render)

        ttk.Label(controls, text="Node ID").grid(row=2, column=0, sticky="w", padx=(0, 10))
        node_picker = ttk.Spinbox(
            controls, from_=0, to=255, textvariable=self.node_id, width=8,
            command=self.render,
        )
        node_picker.grid(row=2, column=1, sticky="w", pady=3)
        node_picker.bind("<KeyRelease>", self.render)

        self.add_slider(controls, 3, "Temperatura", self.temperature, -20, 50, "°C")
        self.add_slider(controls, 4, "Wilgotność", self.humidity, 0, 100, "%")
        self.add_slider(controls, 5, "Napięcie", self.voltage, 0, 4.4, "V")
        self.add_slider(controls, 6, "CPU", self.cpu, 0, 100, "%")
        self.add_slider(controls, 7, "RAM", self.ram, 0, 100, "%")

        ttk.Label(
            controls,
            text="Podgląd używa tego samego kodu rysującego co ekran OLED w gatewayu.",
            wraplength=270,
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(12, 0))

        self.oled = PreviewOLED.__new__(PreviewOLED)
        self.oled.device = PreviewDevice(self.show_frame)
        self.oled.available = True
        self.oled.node_packets = {}
        self.oled.preview_cpu = 18
        self.oled.preview_ram = 42

        self.render()

    def add_slider(self, parent, row, label, variable, minimum, maximum, suffix):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10))

        value_text = tk.StringVar()

        def changed(raw_value):
            value = float(raw_value)
            if suffix == "°C":
                value_text.set(f"{value:.1f} {suffix}")
            elif suffix == "V":
                value_text.set(f"{value:.2f} {suffix}")
            else:
                value_text.set(f"{value:.0f} {suffix}")
            if hasattr(self, "oled"):
                self.render()

        scale = ttk.Scale(
            parent, from_=minimum, to=maximum, variable=variable,
            command=changed,
        )
        scale.grid(row=row, column=1, sticky="ew", pady=4)
        changed(variable.get())
        value = ttk.Label(parent, textvariable=value_text, width=9)
        value.grid(row=row, column=2, sticky="e", padx=(5, 0))

    def show_frame(self, image):
        scaled = image.resize(
            (image.width * self.SCALE, image.height * self.SCALE),
            Image.Resampling.NEAREST,
        ).convert("RGB")
        self.photo = ImageTk.PhotoImage(scaled)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

    def render(self, _event=None):
        try:
            node_id = str(max(0, min(255, int(self.node_id.get()))))
        except (ValueError, tk.TclError):
            node_id = "1"

        packet = {
            "status": 0x1F,
            "aht_temperature": self.temperature.get(),
            "aht_humidity": self.humidity.get(),
            "bmp_pressure": 101325,
            "ds_temperature": 18.7,
            "light": 64,
            "ina1_voltage": self.voltage.get(),
            "ina1_current": 0.14,
            "ina2_voltage": 5.0,
            "ina2_current": 0.32,
            "ina3_voltage": 3.3,
            "ina3_current": 0.08,
            "sequence": 128,
        }
        self.oled.node_packets = {node_id: packet}
        self.oled.preview_cpu = self.cpu.get()
        self.oled.preview_ram = self.ram.get()

        screen = self.screen_name.get()
        if screen == "Pogoda":
            self.oled._draw_node_dashboard(node_id, packet, "weather")
        elif screen == "Zasilanie":
            self.oled._draw_node_dashboard(node_id, packet, "power")
        elif screen == "System":
            self.oled._draw_system_dashboard()
        else:
            self.oled._draw_splash()


if __name__ == "__main__":
    window = tk.Tk()
    OLEDEmulator(window)
    window.mainloop()
