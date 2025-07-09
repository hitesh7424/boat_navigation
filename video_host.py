#!/usr/bin/env python3
import time
import cv2
import platform
from flask import Flask, Response
import threading

# Platform detection
IS_RPI = platform.system() != "Windows"

# Flask App
app = Flask(__name__)
lock = threading.Lock()

if IS_RPI:
    from picamera2 import Picamera2
    picam2 = Picamera2()

    config = picam2.create_video_configuration(
        main={"size": (4608, 2592)},
        controls={"FrameDurationLimits": (33333, 33333)}  # ~30 fps
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1)
else:
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

def generate_frames():
    while True:
        with lock:
            if IS_RPI:
                frame = picam2.capture_array()
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                success, frame = cam.read()
                if not success:
                    continue

        # Resize to 640x480
        frame_resized = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_AREA)

        # Encode JPEG
        ret, buffer = cv2.imencode('.jpg', frame_resized)
        frame_bytes = buffer.tobytes()

        # Yield multipart MJPEG frame
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return '''
    <html>
        <head><title>Universal Camera Stream (640x480)</title></head>
        <body>
            <h2>Live Stream</h2>
            <img src="/video_feed">
        </body>
    </html>
    '''

if __name__ == '__main__':
    platform_name = "Raspberry Pi" if IS_RPI else "Windows Laptop"
    print(f"[VideoHost] Starting stream from {platform_name} at http://<device-ip>:8001")
    app.run(host='0.0.0.0', port=8001, threaded=True)
