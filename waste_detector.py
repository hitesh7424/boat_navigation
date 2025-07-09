#!/usr/bin/env python3
import cv2
import numpy as np
import requests
from flask import Flask, jsonify, Response
import threading

app = Flask(__name__)
VIDEO_STREAM_URL = "http://localhost:8001/video_feed"  # From video_host.py
latest_direction = "FORWARD"
lock = threading.Lock()

# Waste Detection with dynamic exclusion
def detect_waste(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    total_pixels = hsv.shape[0] * hsv.shape[1]

    ranges = {
        "red":    (np.array([0, 50, 50]),   np.array([10, 255, 255])),
        "yellow": (np.array([20, 50, 50]),  np.array([40, 255, 255])),
        "green":  (np.array([40, 50, 50]),  np.array([90, 255, 255])),
        "blue":   (np.array([100, 50, 50]), np.array([130, 255, 255])),
        "white":  (np.array([0, 0, 200]),   np.array([180, 30, 255])),
        "gray":   (np.array([0, 0, 80]),    np.array([180, 30, 200])),
    }

    masks = {c: cv2.inRange(hsv, lo, hi) for c, (lo, hi) in ranges.items()}
    areas = {c: cv2.countNonZero(m) for c, m in masks.items()}
    sorted_areas = sorted(areas.items(), key=lambda x: x[1], reverse=True)

    exclude = set()
    if sorted_areas:
        if sorted_areas[0][1] / total_pixels > 0.5:
            exclude.add(sorted_areas[0][0])
        if len(sorted_areas) > 1 and sorted_areas[1][1] / total_pixels > 0.3:
            exclude.add(sorted_areas[1][0])

    final_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for c, m in masks.items():
        if c not in exclude:
            final_mask |= m

    contours, _ = cv2.findContours(final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [cnt for cnt in contours if cv2.contourArea(cnt) > 500]

# Decide direction based on object position
def navigate(waste_objects, width):
    bins = {"LEFT": 0, "FORWARD": 0, "RIGHT": 0}
    for cnt in waste_objects:
        x, _, w, _ = cv2.boundingRect(cnt)
        cx = x + w // 2
        if cx < width / 3:
            bins["RIGHT"] += 1
        elif cx < 2 * width / 3:
            bins["FORWARD"] += 1
        else:
            bins["LEFT"] += 1
    return min(bins, key=bins.get)

# MJPEG processor + visualizer
def processed_video_stream():
    global latest_direction
    stream = requests.get(VIDEO_STREAM_URL, stream=True)
    byte_data = bytes()

    for chunk in stream.iter_content(chunk_size=1024):
        byte_data += chunk
        start = byte_data.find(b'\xff\xd8')
        end = byte_data.find(b'\xff\xd9')

        if start != -1 and end != -1:
            jpg = byte_data[start:end+2]
            byte_data = byte_data[end+2:]
            img_array = np.frombuffer(jpg, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if frame is None:
                continue

            with lock:
                waste_objects = detect_waste(frame)
                direction = navigate(waste_objects, frame.shape[1])
                latest_direction = direction

            # Annotate frame
            for cnt in waste_objects:
                x, y, w, h = cv2.boundingRect(cnt)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0,255,0), 2)

            cv2.putText(frame, f"Direction: {latest_direction}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return '''
    <html>
        <head><title>Universal Camera Stream (640x480)</title></head>
        <body>
            <h2>Live Stream</h2>
            <img src="/processed_video">
        </body>
    </html>
    '''

# GET /analyze → returns JSON direction
@app.route("/analyze", methods=["GET"])
def analyze():
    with lock:
        return jsonify({"direction": latest_direction})

# GET /processed_video → MJPEG stream of annotated frame
@app.route("/processed_video")
def processed_video():
    return Response(processed_video_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/ping")
def ping():
    return "Waste detector and visual stream online"

if __name__ == "__main__":
    print("[WasteDetector] Running at:")
    print("   - Direction API:       http://<ip>:8002/analyze")
    print("   - Processed video feed: http://<ip>:8002/processed_video")
    app.run(host="0.0.0.0", port=8002, threaded=True)
