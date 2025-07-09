# navigation_core.py
# RESTful navigation decision module

import requests
import time
import threading
from flask import Flask, jsonify

app = Flask(__name__)
PORT = 8008

# Thresholds based on 1.5m x 2.5m boat size
SAFE_FRONT = 120
SAFE_SIDE = 80
SAFE_BACK = 100
SAFE_BIN = 20

# REST endpoints
ENDPOINTS = {
    "direction": "http://localhost:8002/analyze",
    "ultrasonic": "http://localhost:8004/distance",
    "compass": "http://localhost:8005/heading",
    "gps": "http://localhost:8006/location"
}

navigation_state = {
    "direction": "FORWARD",
    "mode": "sensor",  # 'sensor' or 'vision_only'
    "sensors": {},
    "timestamp": time.time()
}

# ----------------- Sensor Fetch -----------------
def fetch_json(url):
    try:
        r = requests.get(url, timeout=1.5)
        if r.status_code == 200:
            return r.json()
    except:
        return None

# ----------------- Navigation Logic -----------------
def decide_direction():
    global navigation_state
    
    us = fetch_json(ENDPOINTS["ultrasonic"])
    direction_data = fetch_json(ENDPOINTS["direction"])
    compass = fetch_json(ENDPOINTS["compass"])
    gps = fetch_json(ENDPOINTS["gps"])

    # Fail flags
    sensor_fail = us is None or any(us[k] is None for k in us)
    compass_fail = compass is None or compass.get("heading") is None
    gps_fail = gps is None or gps.get("lat") is None

    # Store raw sensor state
    navigation_state["sensors"] = {
        "ultrasonic": us,
        "compass": compass,
        "gps": gps
    }

    # If sensor failure → fallback to vision-only
    if sensor_fail:
        navigation_state["mode"] = "vision_only"
        direction = direction_data.get("direction", "FORWARD") if direction_data else "FORWARD"
        navigation_state["direction"] = direction
        return direction

    # Normal mode
    navigation_state["mode"] = "sensor"

    # Obstacle logic
    front = us.get("front", 0)
    left = us.get("left", 0)
    right = us.get("right", 0)
    back = us.get("back", 0)

    # Default to waste-based direction
    dir_from_cam = direction_data.get("direction", "FORWARD") if direction_data else "FORWARD"

    if front >= SAFE_FRONT:
        direction = dir_from_cam
    elif left >= SAFE_SIDE and right < SAFE_SIDE:
        direction = "LEFT"
    elif right >= SAFE_SIDE and left < SAFE_SIDE:
        direction = "RIGHT"
    elif left >= SAFE_SIDE and right >= SAFE_SIDE:
        direction = "LEFT"  # Prefer left on tie
    elif back >= SAFE_BACK:
        direction = "BACK"
    else:
        direction = "STOP"

    navigation_state["direction"] = direction
    return direction

# ----------------- API -----------------
@app.route("/navigate")
def navigate():
    direction = decide_direction()
    navigation_state["timestamp"] = time.time()
    return jsonify({
        "direction": direction,
        "mode": navigation_state["mode"],
        "safe": direction != "STOP"
    })

@app.route("/ping")
def ping():
    return "Navigation core online"

# ----------------- Main -----------------
if __name__ == "__main__":
    print(f"🚀 Navigation Core running on http://<ip>:8008/navigate")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
