# navigation_server.py
# RESTful navigation decision system for autonomous pond boat
# Gathers sensor and vision data, computes optimal movement direction

import requests
import cv2
import numpy as np
from flask import Flask, jsonify, Response
import time

app = Flask(__name__)

# ---------------------------- Configuration ----------------------------
VIDEO_FEED_URL = "http://localhost:8001/video_feed"
WASTE_DIRECTION_URL = "http://localhost:8002/analyze"
ULTRASONIC_URL = "http://localhost:8004/distance"
COMPASS_URL = "http://localhost:8005/heading"
GPS_URL = "http://localhost:8006/location"

SAFE_DISTANCE_CM = 100   # Boat is 1.5m wide, 2.5m long
BOAT_PORT = 8008

# ---------------------------- Helper Functions ----------------------------
def fetch_json(url, timeout=1.5):
    try:
        res = requests.get(url, timeout=timeout)
        return res.json()
    except:
        return None

def is_ultrasonic_safe(distances):
    if not distances:
        return False
    for pos, dist in distances.items():
        if dist is None or dist < SAFE_DISTANCE_CM:
            return False
    return True

def fetch_video_frame():
    try:
        stream = requests.get(VIDEO_FEED_URL, stream=True, timeout=3)
        byte_data = bytes()
        for chunk in stream.iter_content(chunk_size=1024):
            byte_data += chunk
            a = byte_data.find(b'\xff\xd8')
            b = byte_data.find(b'\xff\xd9')
            if a != -1 and b != -1:
                jpg = byte_data[a:b+2]
                byte_data = byte_data[b+2:]
                frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                return frame
    except:
        return None

# ---------------------------- Vision Fallback ----------------------------
def fallback_camera_direction(frame):
    if frame is None:
        return "STOP", 0.0, "Camera feed unavailable"

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (30, 30, 30), (180, 255, 255))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return "FORWARD", 0.5, "No major obstacle visually"

    left, center, right = 0, 0, 0
    width = frame.shape[1]
    for cnt in contours:
        x, _, w, _ = cv2.boundingRect(cnt)
        cx = x + w//2
        if cx < width // 3:
            left += 1
        elif cx < 2 * width // 3:
            center += 1
        else:
            right += 1

    direction = min((left, "RIGHT"), (center, "FORWARD"), (right, "LEFT"))[1]
    confidence = 0.6 if center == 0 else 0.8
    reason = "Visual fallback used to navigate around obstacles"
    return direction, confidence, reason

# ---------------------------- Main Navigation Endpoint ----------------------------
@app.route("/navigate", methods=["GET"])
def navigate():
    result = {
        "direction": "STOP",
        "mode": "normal",
        "confidence": 0.0,
        "reason": "unknown",
        "sensor_status": {
            "ultrasonic": False,
            "compass": False,
            "gps": False
        }
    }

    # Fetch direction from waste detector
    waste_data = fetch_json(WASTE_DIRECTION_URL)
    direction = waste_data.get("direction") if waste_data else None

    # Fetch ultrasonic data
    distances = fetch_json(ULTRASONIC_URL)
    ultrasonic_ok = is_ultrasonic_safe(distances)
    result["sensor_status"]["ultrasonic"] = ultrasonic_ok

    # Fetch compass heading
    compass = fetch_json(COMPASS_URL)
    compass_ok = compass is not None and compass.get("heading") is not None
    result["sensor_status"]["compass"] = compass_ok

    # Fetch GPS location
    gps = fetch_json(GPS_URL)
    gps_ok = gps is not None and gps.get("lat") and gps.get("lon")
    result["sensor_status"]["gps"] = gps_ok

    # Fail-safe logic
    if not ultrasonic_ok or not compass_ok or not gps_ok:
        frame = fetch_video_frame()
        fallback_dir, conf, reason = fallback_camera_direction(frame)
        result.update({
            "direction": fallback_dir,
            "mode": "vision_fallback",
            "confidence": conf,
            "reason": reason
        })
        return jsonify(result)

    # All sensors OK → Use waste direction
    if direction:
        result.update({
            "direction": direction,
            "confidence": 0.95,
            "reason": "Sensor data valid, waste direction used"
        })
    else:
        result.update({
            "direction": "FORWARD",
            "confidence": 0.5,
            "reason": "Waste detection unavailable, assuming FORWARD"
        })

    return jsonify(result)

# ---------------------------- Health Check ----------------------------
@app.route("/ping")
def ping():
    return "Navigation system online"

# ---------------------------- Server Launch ----------------------------
if __name__ == "__main__":
    print(f"🚀 Navigation server running at http://0.0.0.0:{BOAT_PORT}/navigate")
    app.run(host="0.0.0.0", port=BOAT_PORT, threaded=True)
