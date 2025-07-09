# camera_navigator.py
# Provides fallback visual navigation direction based on obstacle-free zones in camera feed.
# This module is imported by navigation_server when sensor data is unavailable.

import cv2
import numpy as np
import requests

VIDEO_FEED_URL = "http://localhost:8001/video_feed"

# Fetch frame from video host
def fetch_frame():
    try:
        stream = requests.get(VIDEO_FEED_URL, stream=True, timeout=3)
        byte_data = b''
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

# Analyze image for obstacle-free direction (left, forward, right)
def analyze_direction(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (30, 30, 30), (180, 255, 255))  # generic obstacle mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bins = {"LEFT": 0, "FORWARD": 0, "RIGHT": 0}
    width = frame.shape[1]

    for cnt in contours:
        x, _, w, _ = cv2.boundingRect(cnt)
        cx = x + w // 2
        if cx < width / 3:
            bins["LEFT"] += 1
        elif cx < 2 * width / 3:
            bins["FORWARD"] += 1
        else:
            bins["RIGHT"] += 1

    direction = min(bins, key=bins.get)
    confidence = 1.0 - (bins[direction] / max(1, sum(bins.values())))
    reason = "Visual fallback logic"
    return direction, confidence, reason

# Top-level method used by navigation_server

def get_direction():
    frame = fetch_frame()
    if frame is None:
        return "STOP", 0.0, "No camera feed"
    return analyze_direction(frame)
