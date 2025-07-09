#!/usr/bin/env python3
import cv2
import requests
import os
import time
import numpy as np
import threading
from flask import Flask, jsonify
from datetime import datetime

# Settings
VIDEO_FEED_URL = "http://localhost:8002/processed_video"
RECORDING_FOLDER = "recordings"
SEGMENT_DURATION = 5 * 60  # 5 minutes in seconds
STATUS_PORT = 8003

# Flask App
app = Flask(__name__)
status_lock = threading.Lock()
recording_status = {
    "recording": False,
    "last_saved": None
}

# Ensure recording folder exists
os.makedirs(RECORDING_FOLDER, exist_ok=True)

# Utility to check stream availability
def is_stream_live(url):
    try:
        r = requests.get(url, stream=True, timeout=5)
        return r.status_code == 200
    except:
        return False

# Recording loop
def recording_loop():
    global recording_status
    cap = None
    byte_data = b''

    while True:
        if is_stream_live(VIDEO_FEED_URL):
            print("[🎥] Stream is live. Starting capture...")
            stream = requests.get(VIDEO_FEED_URL, stream=True)
            byte_data = b''
            segment_start = time.time()
            filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".mp4"
            filepath = os.path.join(RECORDING_FOLDER, filename)

            out = cv2.VideoWriter(filepath,
                                  cv2.VideoWriter_fourcc(*'mp4v'),
                                  20.0, (640, 480))  # Match stream size

            with status_lock:
                recording_status["recording"] = True
                recording_status["last_saved"] = filename

            for chunk in stream.iter_content(chunk_size=1024):
                byte_data += chunk
                a = byte_data.find(b'\xff\xd8')
                b = byte_data.find(b'\xff\xd9')
                if a != -1 and b != -1:
                    jpg = byte_data[a:b+2]
                    byte_data = byte_data[b+2:]
                    frame = cv2.imdecode(
                        np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        out.write(frame)

                    if time.time() - segment_start >= SEGMENT_DURATION:
                        print(f"[✅] Saved segment: {filename}")
                        out.release()
                        break
        else:
            print("[⚠️] Stream not available. Retrying in 5 seconds.")
            with status_lock:
                recording_status["recording"] = False
            time.sleep(5)

# API: Recording status
@app.route("/status", methods=["GET"])
def status():
    with status_lock:
        return jsonify(recording_status)

@app.route("/", methods=["GET"])
def rec():
    return jsonify(recording_status)

# Start everything
if __name__ == "__main__":
    print("📽️  Video Recorder started...")
    threading.Thread(target=recording_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=STATUS_PORT, threaded=True)
