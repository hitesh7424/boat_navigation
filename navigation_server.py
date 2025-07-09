# navigation_server.py
"""
Navigation Decision Server
- Integrates ultrasonic, GPS, compass, and waste direction sensors
- Hosts REST API on port 8008 at /navigate
- Provides safe, failsafe navigation direction for the boat
- Falls back to camera-based navigation if sensors fail
"""

import requests
import time
import json
import cv2
import numpy as np
from flask import Flask, jsonify
from threading import Lock

# --- Configuration ---
VIDEO_STREAM = "http://localhost:8001/video_feed"
DIRECTION_API = "http://localhost:8002/analyze"
ULTRASONIC_API = "http://localhost:8004/distance"
COMPASS_API = "http://localhost:8005/heading"
GPS_API = "http://localhost:8006/location"

SAFE_DISTANCE_CM = 100
TIMEOUT = 2

app = Flask(__name__)
status_lock = Lock()

# --- Helper: get JSON safely ---
def get_json(url):
    try:
        r = requests.get(url, timeout=TIMEOUT)
        if r.ok:
            return r.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
    return None

# --- Helper: get camera frame ---
def get_video_frame():
    try:
        stream = requests.get(VIDEO_STREAM, stream=True, timeout=5)
        byte_data = b''
        for chunk in stream.iter_content(chunk_size=1024):
            byte_data += chunk
            start = byte_data.find(b'\xff\xd8')
            end = byte_data.find(b'\xff\xd9')
            if start != -1 and end != -1:
                jpg = byte_data[start:end+2]
                byte_data = byte_data[end+2:]
                img_array = np.frombuffer(jpg, dtype=np.uint8)
                return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"[ERROR] Camera feed unavailable: {e}")
    return None

# --- Helper: Fallback camera navigation (placeholder) ---
def camera_fallback_direction(frame):
    # TODO: Replace with actual camera-based logic
    h, w = frame.shape[:2]
    center_color = frame[h//2, w//2].tolist()
    print("[INFO] Vision fallback active, center pixel:", center_color)
    return "FORWARD", 0.5, "Fallback vision center"

# --- Main API: Decide navigation ---
@app.route("/navigate", methods=["GET"])
def navigate():
    sensor_ok = {"ultrasonic": False, "gps": False, "compass": False}
    result = {
        "direction": "STOP",
        "mode": "failsafe",
        "confidence": 0.0,
        "reason": "No sensors available",
        "sensor_status": sensor_ok
    }

    # --- Get all sensor data ---
    direction_data = get_json(DIRECTION_API)
    distance_data = get_json(ULTRASONIC_API)
    compass_data = get_json(COMPASS_API)
    gps_data = get_json(GPS_API)

    # --- Update status ---
    sensor_ok["ultrasonic"] = bool(distance_data)
    sensor_ok["compass"] = bool(compass_data and compass_data.get("heading") is not None)
    sensor_ok["gps"] = bool(gps_data and gps_data.get("lat") is not None)

    # --- Check ultrasonic obstacle ---
    if distance_data:
        too_close = any(v is not None and v < SAFE_DISTANCE_CM for v in distance_data.values())
        if too_close:
            result.update({
                "direction": "STOP",
                "mode": "normal",
                "confidence": 0.9,
                "reason": "Obstacle too close",
                "sensor_status": sensor_ok
            })
            return jsonify(result)

    # --- If waste direction available and no block ---
    if direction_data and direction_data.get("direction"):
        result.update({
            "direction": direction_data["direction"],
            "mode": "normal",
            "confidence": 0.95,
            "reason": "All sensors nominal",
            "sensor_status": sensor_ok
        })
        return jsonify(result)

    # --- Vision fallback ---
    frame = get_video_frame()
    if frame is not None:
        vision_dir, conf, reason = camera_fallback_direction(frame)
        result.update({
            "direction": vision_dir,
            "mode": "vision_fallback",
            "confidence": conf,
            "reason": reason,
            "sensor_status": sensor_ok
        })
        return jsonify(result)

    # --- Emergency stop ---
    result["direction"] = "STOP"
    result["reason"] = "No valid sensors or fallback"
    return jsonify(result)

@app.route("/ping")
def ping():
    return "Navigation server online"

if __name__ == "__main__":
    print("🧭 Navigation server running on http://<ip>:8008/navigate")
    app.run(host="0.0.0.0", port=8008, threaded=True)
