#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
import threading
from flask import Flask, jsonify

app = Flask(__name__)
GPIO.setmode(GPIO.BCM)

# Sensor GPIO setup
sensors = {
    "front":    {"trigger": 5,  "echo": 6},
    "left":     {"trigger": 13, "echo": 19},
    "right":    {"trigger": 16, "echo": 20},
    "back":     {"trigger": 21, "echo": 26},
    "dustbin":  {"trigger": 17, "echo": 27},
}

# Initialize GPIO pins
for s in sensors.values():
    GPIO.setup(s["trigger"], GPIO.OUT)
    GPIO.setup(s["echo"], GPIO.IN)
    GPIO.output(s["trigger"], False)

distance_data = {key: None for key in sensors}
lock = threading.Lock()

# Measure distance
def measure_distance(trigger_pin, echo_pin):
    GPIO.output(trigger_pin, True)
    time.sleep(0.00001)
    GPIO.output(trigger_pin, False)

    start_time = time.time()
    stop_time = time.time()

    timeout = start_time + 0.04
    while GPIO.input(echo_pin) == 0 and time.time() < timeout:
        start_time = time.time()
    while GPIO.input(echo_pin) == 1 and time.time() < timeout:
        stop_time = time.time()

    elapsed = stop_time - start_time
    distance = round((elapsed * 34300) / 2, 2)  # in cm
    return distance if distance < 400 else None  # cap at 4m

# Update readings periodically
def sensor_loop():
    global distance_data
    while True:
        with lock:
            for name, pins in sensors.items():
                dist = measure_distance(pins["trigger"], pins["echo"])
                distance_data[name] = dist
        time.sleep(0.2)  # Sampling delay

@app.route("/distance", methods=["GET"])
def get_distances():
    with lock:
        return jsonify(distance_data)

@app.route("/ping")
def ping():
    return "Ultrasonic sensor host online"

if __name__ == "__main__":
    print("📡 Ultrasonic sensor server running on http://<pi-ip>:8004/distance")
    threading.Thread(target=sensor_loop, daemon=True).start()
    try:
        app.run(host="0.0.0.0", port=8004, threaded=True)
    finally:
        GPIO.cleanup()
