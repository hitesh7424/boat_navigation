#!/usr/bin/env python3
import serial
import time
import threading
from flask import Flask, jsonify
import pynmea2

app = Flask(__name__)
gps_data = {"lat": None, "lon": None, "fix": False}
lock = threading.Lock()

# Update with actual serial port if needed
GPS_PORT = "/dev/serial0"
BAUD_RATE = 9600

def gps_loop():
    global gps_data
    try:
        with serial.Serial(GPS_PORT, BAUD_RATE, timeout=1) as ser:
            while True:
                try:
                    line = ser.readline().decode("ascii", errors="ignore").strip()
                    if line.startswith("$GPGGA") or line.startswith("$GNGGA"):
                        msg = pynmea2.parse(line)
                        if msg.lat and msg.lon and int(msg.gps_qual) > 0:
                            lat = msg.latitude
                            lon = msg.longitude
                            with lock:
                                gps_data["lat"] = round(lat, 6)
                                gps_data["lon"] = round(lon, 6)
                                gps_data["fix"] = True
                        else:
                            with lock:
                                gps_data["fix"] = False
                except Exception as e:
                    print("GPS parse error:", e)
    except serial.SerialException as e:
        print("GPS serial error:", e)

@app.route("/")
def location_home():
    with lock:
        return jsonify(gps_data)

@app.route("/location")
def location():
    with lock:
        return jsonify(gps_data)

@app.route("/ping")
def ping():
    return "GPS module online"

if __name__ == "__main__":
    print("📡 GPS data host running on http://<pi-ip>:8006/location")
    threading.Thread(target=gps_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8006, threaded=True)
