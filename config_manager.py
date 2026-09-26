import copy
import json
import os
import tempfile

DEFAULT_CONFIG = {
    "web": {
        "port": 8080
    },
    "nrf": {
        "ce_pin": 22,
        "csn_pin": 1,
        "channel": 50,
        "address": "WTHLS",
        "power": 2,
        "data_rate": 0,
        "payload_size": 32,
        "auto_ack": True,
        "retry_delay": 5,
        "retry_count": 15
    },
    "mqtt": {
        "enabled": False,
        "host": "127.0.0.1",
        "port": 1883,
        "username": "",
        "password": "",
        "base_topic": "WeatherLink",
        "client_id": "weatherlink-gateway",
        "qos": 1,
        "retain": True
    },
    "oled": {
        "enabled": True,
        "i2c_bus": 1,
        "address": "0x3C",
        "width": 128,
        "height": 64,
        "rotation": 0,
        "page_seconds": 4
    }
}

class ConfigManager:
    def __init__(self, path="settings.json"):
        self.path = path
        self.data = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            self.save()
            return
        with open(self.path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self._merge(self.data, loaded)

    def _merge(self, target, source):
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                self._merge(target[key], value)
            else:
                target[key] = value

    def save(self):
        directory = os.path.dirname(os.path.abspath(self.path)) or "."
        fd, tmp = tempfile.mkstemp(prefix=".settings-", dir=directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def get(self, key, default=None):
        value = self.data
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value

    def get_int(self, key, default=0):
        try:
            return int(self.get(key, default))
        except (TypeError, ValueError):
            return default

    def public(self, include_secrets=False):
        out = copy.deepcopy(self.data)
        if not include_secrets:
            out["mqtt"]["password"] = "" if out["mqtt"].get("password") else ""
        return out

    def update_from_web(self, p):
        nrf = p.get("nrf", {})
        mqtt = p.get("mqtt", {})
        oled = p.get("oled", {})
        web = p.get("web", {})

        if nrf:
            self.data["nrf"]["ce_pin"] = int(nrf.get("ce_pin", self.get_int("nrf.ce_pin")))
            self.data["nrf"]["csn_pin"] = int(nrf.get("csn_pin", self.get_int("nrf.csn_pin")))
            self.data["nrf"]["channel"] = max(0, min(125, int(nrf.get("channel", 50))))
            self.data["nrf"]["address"] = str(nrf.get("address", "WTHLS"))[:5]
            self.data["nrf"]["power"] = max(0, min(3, int(nrf.get("power", 2))))
            self.data["nrf"]["data_rate"] = max(0, min(2, int(nrf.get("data_rate", 0))))
            self.data["nrf"]["auto_ack"] = bool(nrf.get("auto_ack", True))
            self.data["nrf"]["retry_delay"] = max(0, min(15, int(nrf.get("retry_delay", 5))))
            self.data["nrf"]["retry_count"] = max(0, min(15, int(nrf.get("retry_count", 15))))

        if mqtt:
            self.data["mqtt"]["enabled"] = bool(mqtt.get("enabled", False))
            self.data["mqtt"]["host"] = str(mqtt.get("host", "127.0.0.1")).strip()
            self.data["mqtt"]["port"] = int(mqtt.get("port", 1883))
            self.data["mqtt"]["username"] = str(mqtt.get("username", ""))
            if "password" in mqtt and mqtt["password"] != "":
                self.data["mqtt"]["password"] = str(mqtt["password"])
            self.data["mqtt"]["base_topic"] = str(mqtt.get("base_topic", "WeatherLink")).strip().strip("/")
            self.data["mqtt"]["client_id"] = str(mqtt.get("client_id", "weatherlink-gateway")).strip()
            self.data["mqtt"]["qos"] = max(0, min(2, int(mqtt.get("qos", 1))))
            self.data["mqtt"]["retain"] = bool(mqtt.get("retain", True))

        if oled:
            self.data["oled"]["enabled"] = bool(oled.get("enabled", True))
            self.data["oled"]["i2c_bus"] = int(oled.get("i2c_bus", 1))
            self.data["oled"]["address"] = str(oled.get("address", "0x3C"))
            self.data["oled"]["width"] = int(oled.get("width", 128))
            self.data["oled"]["height"] = int(oled.get("height", 64))
            self.data["oled"]["rotation"] = int(oled.get("rotation", 0))
            self.data["oled"]["page_seconds"] = max(1, int(oled.get("page_seconds", 4)))

        if web:
            self.data["web"]["port"] = int(web.get("port", 8080))
