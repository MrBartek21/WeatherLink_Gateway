#!/usr/bin/env python3
import atexit
import os
import signal
import threading
import time
from flask import Flask, jsonify, render_template, request

from config_manager import ConfigManager
from mqtt_manager import MQTTManager
from nrf_receiver import NRFReceiver
from oled_display import OLEDDisplay

APP_NAME = "WeatherLink Gateway"

config = ConfigManager("settings.json")
mqtt = MQTTManager(config)
nrf = NRFReceiver(
    ce_pin=config.get_int("nrf.ce_pin", 22),
    csn_pin=config.get_int("nrf.csn_pin", 1),
)
oled = OLEDDisplay(config)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

state_lock = threading.Lock()
state = {
    "connected": False,
    "last_data": None,
    "last_update": None,
    "last_raw": None,
    "nodes": {},
    "error": nrf.init_error,
    "stats": {},
    "mqtt": {"connected": False, "enabled": False},
    "oled": {"enabled": False, "available": False},
}

def update_state(data, raw_text):
    with state_lock:
        node_id = str(data.get("node_id", 0))
        data = dict(data)
        data["received_at"] = time.time()
        state["connected"] = True
        state["last_data"] = data
        state["nodes"][node_id] = data
        state["last_raw"] = raw_text
        state["last_update"] = time.time()
        state["error"] = None
        state["stats"] = nrf.get_stats()

def receive_loop():
    while True:
        try:
            packet = nrf.receive_packet()
            if packet:
                raw_text = nrf.packet_to_text(packet)
                update_state(packet, raw_text)
                mqtt.publish_packet(packet)
                with state_lock:
                    node_snapshot = {key: dict(value) for key, value in state["nodes"].items()}
                oled.update_nodes(node_snapshot)
            else:
                time.sleep(0.02)
        except Exception as exc:
            with state_lock:
                state["error"] = str(exc)
            time.sleep(1)

def service_loop():
    while True:
        try:
            mqtt.loop()
        except Exception:
            pass
        time.sleep(0.05)

@app.route("/")
def index():
    return render_template("index.html", app_name=APP_NAME)

@app.get("/api/status")
def api_status():
    with state_lock:
        result = dict(state)
        result["stats"] = nrf.get_stats()
        result["mqtt"] = mqtt.status()
        result["oled"] = oled.status()
        result["config"] = config.public()
        if result["last_update"]:
            result["age"] = max(0, time.time() - result["last_update"])
        else:
            result["age"] = None
        return jsonify(result)

@app.get("/api/config")
def api_config():
    return jsonify(config.public(include_secrets=False))

@app.post("/api/config")
def api_config_save():
    payload = request.get_json(silent=True) or {}
    try:
        config.update_from_web(payload)
        config.save()
        mqtt.apply_config()
        oled.apply_config()
        return jsonify({"ok": True, "message": "Konfiguracja zapisana. Uruchom ponownie usługi, aby zastosować konfigurację NRF24."})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

@app.post("/api/restart")
def api_restart():
    def delayed_restart():
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)
    threading.Thread(target=delayed_restart, daemon=True).start()
    return jsonify({"ok": True})

@app.post("/api/mqtt/test")
def api_mqtt_test():
    ok, message = mqtt.test_publish()
    return jsonify({"ok": ok, "message": message}), (200 if ok else 400)

@app.post("/api/oled/test")
def api_oled_test():
    ok, message = oled.test()
    return jsonify({"ok": ok, "message": message}), (200 if ok else 400)

def shutdown(*_args):
    try:
        mqtt.stop()
    except Exception:
        pass
    try:
        oled.stop()
    except Exception:
        pass

atexit.register(shutdown)

if __name__ == "__main__":
    threading.Thread(target=receive_loop, daemon=True).start()
    threading.Thread(target=service_loop, daemon=True).start()
    print(f"{APP_NAME} starting on http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=config.get_int("web.port", 8080), threaded=True)
