# pondbot_motor_control.py
"""
Modernized PondBot Motor Control Library
Supports asynchronous (non-blocking) motor operations with optional blocking mode.
Compatible with serial (/dev/ttyUSB0) and HTTP fallback to ESP32 control.
"""

import os
import socket
import time
import threading
import requests
import serial

# ---- Configuration ----
SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 115200
SERIAL_TIMEOUT = 2
ESP_LAST_OCTET = 35
HTTP_TIMEOUT = 2
RETRY_DELAY = 2

# ---- Network Helpers ----
def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

def get_esp_ip() -> str:
    parts = get_local_ip().split('.')
    parts[-1] = str(ESP_LAST_OCTET)
    return '.'.join(parts)

ESP_IP = get_esp_ip()

# ---- Connectivity Checks ----
def is_serial_connected() -> bool:
    return os.path.exists(SERIAL_PORT)

def ping_http() -> bool:
    try:
        r = requests.get(f"http://{ESP_IP}", timeout=HTTP_TIMEOUT)
        return r.status_code in (200, 404)
    except:
        return False

def get_connection_method() -> str:
    if is_serial_connected():
        return 'serial'
    if ping_http():
        return 'http'
    return 'none'

# ---- Low-Level Send ----
def send_serial(cmd: str) -> str:
    try:
        with serial.Serial(SERIAL_PORT, BAUDRATE, timeout=SERIAL_TIMEOUT) as ser:
            ser.write((cmd + "\n").encode())
            time.sleep(0.1)
            return ser.read_all().decode().strip()
    except serial.SerialException as e:
        return f"<Serial error: {e}>"

def send_http(endpoint: str, params: dict) -> str:
    url = f"http://{ESP_IP}/{endpoint}"
    try:
        r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
        return r.text.strip()
    except requests.RequestException as e:
        return f"<HTTP error: {e}>"

def dispatch(cmd: str, endpoint: str, params: dict) -> str:
    method = get_connection_method()
    if method == 'serial':
        return send_serial(cmd)
    elif method == 'http':
        return send_http(endpoint, params)
    return "<Error: No connection available>"

# ---- Device Definitions ----
MOTOR_IDS = {
    "p_right": 0,
    "p_left": 1,
    "bin_hoist": 2,
    "conv_move": 3,
    "conv_hoist": 4,
    "magnet_hoist": 5
}

ACTION_MAP = {
    "fwd": (1, 0),
    "rev": (0, 1),
    "stop": (1, 1)
}

# ---- Core Control ----
def control_device(name: str, action: str) -> str:
    if name not in MOTOR_IDS:
        return f"[Error] Unknown device '{name}'"
    if action not in ACTION_MAP:
        return f"[Error] Unknown action '{action}'"
    idx = MOTOR_IDS[name]
    a, b = ACTION_MAP[action]
    cmd = f"{name} {action}"
    return dispatch(cmd, "relay", {"i": idx, "a": a, "b": b})

def run_device(name: str, action: str, duration: float, blocking: bool = True) -> str:
    if blocking:
        out = [control_device(name, action)]
        time.sleep(duration)
        out.append(control_device(name, "stop"))
        return "\n".join(out)
    else:
        def task():
            control_device(name, action)
            time.sleep(duration)
            control_device(name, "stop")
        threading.Thread(target=task, daemon=True).start()
        return f"[Info] {name} running '{action}' for {duration}s (non-blocking)"

# ---- Macros ----
def boat_forward(duration: float = None, blocking: bool = True) -> str:
    if duration:
        return run_device("p_left", "fwd", duration, blocking) + "\n" + \
               run_device("p_right", "fwd", duration, blocking)
    return control_device("p_left", "fwd") + "\n" + control_device("p_right", "fwd")

def boat_backward(duration: float = None, blocking: bool = True) -> str:
    if duration:
        return run_device("p_left", "rev", duration, blocking) + "\n" + \
               run_device("p_right", "rev", duration, blocking)
    return control_device("p_left", "rev") + "\n" + control_device("p_right", "rev")

def boat_left(duration: float = None, blocking: bool = True) -> str:
    if duration:
        return run_device("p_left", "rev", duration, blocking) + "\n" + \
               run_device("p_right", "fwd", duration, blocking)
    return control_device("p_left", "rev") + "\n" + control_device("p_right", "fwd")

def boat_right(duration: float = None, blocking: bool = True) -> str:
    if duration:
        return run_device("p_left", "fwd", duration, blocking) + "\n" + \
               run_device("p_right", "rev", duration, blocking)
    return control_device("p_left", "fwd") + "\n" + control_device("p_right", "rev")

def boat_stop() -> str:
    return control_device("p_left", "stop") + "\n" + control_device("p_right", "stop")

def emergency_stop() -> str:
    return "\n".join(control_device(name, "stop") for name in MOTOR_IDS)
