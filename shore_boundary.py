# shore_boundary.py
# Detects shoreline boundary using camera input to keep the boat within safe water area.
# Processes frames from /video_feed and returns shoreline mask + danger signal if near boundary.

import cv2
import numpy as np
import requests
from flask import Flask, Response, jsonify

app = Flask(__name__)
VIDEO_FEED_URL = "http://localhost:8001/video_feed"
SHORE_PORT = 8009

# Configuration
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
BORDER_SAFETY_RATIO = 0.15  # % of frame height considered dangerous near top/bottom (shore proximity)

# Helper function to fetch a single frame from MJPEG stream
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

# Main image processing logic for shoreline detection
def detect_shore(frame):
    # Convert to grayscale and blur
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    
    # Use adaptive thresholding to isolate high-contrast regions (usually shorelines)
    thresh = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        11, 5)

    # Find contours (edges in water or shore)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    proximity_alert = False

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if y < FRAME_HEIGHT * BORDER_SAFETY_RATIO or (y + h) > FRAME_HEIGHT * (1 - BORDER_SAFETY_RATIO):
            proximity_alert = True
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
        else:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

    return frame, proximity_alert

@app.route("/shore_mask")
def shore_mask():
    frame = fetch_video_frame()
    if frame is None:
        return "Could not fetch frame", 500

    processed, alert = detect_shore(frame)
    _, buffer = cv2.imencode(".jpg", processed)
    return Response(buffer.tobytes(), mimetype='image/jpeg')

@app.route("/shore_status")
def shore_status():
    frame = fetch_video_frame()
    if frame is None:
        return jsonify({"status": "error", "message": "Frame not available"}), 500

    _, alert = detect_shore(frame)
    return jsonify({"danger": alert})

@app.route("/")
def index():
    return "Shoreline boundary detection online. Use /shore_status or /shore_mask"

if __name__ == "__main__":
    print(f"🌊 Shore boundary detector running at http://0.0.0.0:{SHORE_PORT}")
    app.run(host="0.0.0.0", port=SHORE_PORT, threaded=True)
