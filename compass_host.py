#!/usr/bin/env python3
import time
import threading
from flask import Flask, jsonify

# Use Adafruit HMC5883L or QMC5883L compatible library
import board
import busio
import adafruit_hmc5883l  # or replace with QMC5883L if needed

app = Flask(__name__)
heading_data = {"heading": None}
lock = threading.Lock()

# Setup I2C compass
i2c = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_hmc5883l.HMC5883L(i2c)

def read_heading_loop():
    while True:
        try:
            mag_x, mag_y, _ = sensor.magnetic
            heading_rad = math.atan2(mag_y, mag_x)
            heading_deg = (heading_rad * 180 / math.pi) % 360
            with lock:
                heading_data["heading"] = round(heading_deg, 2)
        except Exception as e:
            print("Compass read error:", e)
        time.sleep(0.5)

@app.route("/")
def heading_data():
    with lock:
        return jsonify(heading_data)

@app.route("/heading")
def heading():
    with lock:
        return jsonify(heading_data)

@app.route("/ping")
def ping():
    return "Compass heading API online"

if __name__ == "__main__":
    print("🧭 Compass heading host running on http://<pi-ip>:8005/heading")
    threading.Thread(target=read_heading_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8005, threaded=True)
