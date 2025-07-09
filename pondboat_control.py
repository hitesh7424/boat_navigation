#!/usr/bin/env python3
"""
PondBoat Control Module for Raspberry Pi
— Serial (/dev/ttyUSB0) speaks only: fwd, rev, stop
— HTTP fallback: /relay?i=&a=&b=
— ESP32 assumed at same subnet, last octet = .35
"""

import os
import socket
import time

import requests
import serial

# —— Configuration ——
SERIAL_PORT    = "/dev/ttyUSB0"
BAUDRATE       = 115200
SERIAL_TIMEOUT = 2       # seconds
ESP_LAST_OCTET = 35
HTTP_TIMEOUT   = 2       # seconds
RETRY_DELAY    = 2       # seconds between retries

# —— Network Helpers ——
def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except:
        return "127.0.0.1"
    finally:
        s.close()

def get_esp_ip() -> str:
    parts = get_local_ip().split('.')
    if len(parts) != 4:
        raise RuntimeError(f"Bad IP: {parts}")
    parts[-1] = str(ESP_LAST_OCTET)
    return '.'.join(parts)

ESP_IP = get_esp_ip()

# —— Connectivity Checks ——
def is_serial_connected() -> bool:
    """Return True if serial port exists."""
    return os.path.exists(SERIAL_PORT)

def ping_http() -> bool:
    """Return True if ESP is reachable via HTTP."""
    try:
        # simple GET to base URL
        r = requests.get(f"http://{ESP_IP}", timeout=HTTP_TIMEOUT)
        return r.status_code == 200 or r.status_code == 404
    except requests.RequestException:
        return False

def get_connection_method() -> str:
    """Determine current connection method: 'serial', 'http', or 'none'."""
    if is_serial_connected():
        return 'serial'
    if ping_http():
        return 'http'
    return 'none'

def wait_for_connection(retry_delay: float = RETRY_DELAY) -> str:
    """Block until ESP32 is connected via serial or HTTP, retrying as needed.
    Returns the method used once connected.
    """
    while True:
        method = get_connection_method()
        if method in ('serial', 'http'):
            print(f"[Info] Connected to ESP32 via {method.upper()}")
            return method
        print(f"[Warning] No connection to ESP32; retrying in {retry_delay}s...")
        time.sleep(retry_delay)

# —— Low-Level Send ——
def send_serial(cmd: str) -> str:
    """Send 'device fwd|rev|stop' over serial."""
    try:
        with serial.Serial(SERIAL_PORT, BAUDRATE, timeout=SERIAL_TIMEOUT) as ser:
            ser.write((cmd + "\n").encode())
            time.sleep(0.1)
            return ser.read_all().decode().strip()
    except serial.SerialException as e:
        return f"<Serial error: {e}>"

def send_http(endpoint: str, params: dict) -> str:
    """GET http://ESP_IP/endpoint?params..."""
    url = f"http://{ESP_IP}/{endpoint}"
    try:
        r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
        return r.text.strip()
    except requests.RequestException as e:
        return f"<Wi-Fi error: {e}>"

def dispatch(cmd: str, endpoint: str, params: dict) -> str:
    """Use serial if available, else HTTP fallback."""
    method = get_connection_method()
    if method == 'serial':
        return send_serial(cmd)
    if method == 'http':
        return send_http(endpoint, params)
    return "<Error: No connection available>"

# —— Device Definitions ——
MOTOR_IDS = {
    "p_right":      0,
    "p_left":       1,
    "bin_hoist":    2,
    "conv_move":    3,
    "conv_hoist":   4,
    "magnet_hoist": 5,
}

# serial actions and their HTTP (a,b) mappings
ACTION_MAP = {
    "fwd":  (1, 0),
    "rev":  (0, 1),
    "stop": (1, 1),
}

def control_device(name: str, action: str) -> str:
    """
    Send "<name> action" over serial or
    /relay?i=&a=&b= over HTTP.
    """
    if name not in MOTOR_IDS:
        return f"[Error] Unknown device '{name}'"
    if action not in ACTION_MAP:
        return f"[Error] Unknown action '{action}'"
    idx = MOTOR_IDS[name]
    a, b = ACTION_MAP[action]
    cmd = f"{name} {action}"
    return dispatch(cmd, "relay", {"i": idx, "a": a, "b": b})

def run_device(name: str, action: str, duration: float) -> str:
    """
    Run device with `action` for `duration` seconds, then stop.
    """
    out = [control_device(name, action)]
    time.sleep(duration)
    out.append(control_device(name, "stop"))
    return "\n".join(out)

# —— 1. Low-Level Device Controls ——
def control_p_right(action: str, duration: float = None) -> str:
    return run_device("p_right", action, duration) if duration else control_device("p_right", action)

def control_p_left(action: str, duration: float = None) -> str:
    return run_device("p_left", action, duration) if duration else control_device("p_left", action)

def control_bin_hoist(action: str, duration: float = None) -> str:
    return run_device("bin_hoist", action, duration) if duration else control_device("bin_hoist", action)

def control_conv_move(action: str, duration: float = None) -> str:
    return run_device("conv_move", action, duration) if duration else control_device("conv_move", action)

def control_conv_hoist(action: str, duration: float = None) -> str:
    return run_device("conv_hoist", action, duration) if duration else control_device("conv_hoist", action)

def control_magnet_hoist(action: str, duration: float = None) -> str:
    return run_device("magnet_hoist", action, duration) if duration else control_device("magnet_hoist", action)

# —— 2. Boat-Wide Macros ——
def boat_forward(duration: float = None) -> str:
    if duration:
        return run_device("p_left", "fwd", duration) + "\n" + run_device("p_right", "fwd", duration)
    return control_p_left("fwd") + "\n" + control_p_right("fwd")

def boat_backward(duration: float = None) -> str:
    if duration:
        return run_device("p_left", "rev", duration) + "\n" + run_device("p_right", "rev", duration)
    return control_p_left("rev") + "\n" + control_p_right("rev")

def boat_left(duration: float = None) -> str:
    if duration:
        return run_device("p_left", "rev", duration) + "\n" + run_device("p_right", "fwd", duration)
    return control_p_left("rev") + "\n" + control_p_right("fwd")

def boat_right(duration: float = None) -> str:
    if duration:
        return run_device("p_left", "fwd", duration) + "\n" + run_device("p_right", "rev", duration)
    return control_p_left("fwd") + "\n" + control_p_right("rev")

def boat_stop() -> str:
    return control_p_left("stop") + "\n" + control_p_right("stop")

# —— 3. Conveyor Belt & Hoist ——
def start_conveyor(duration: float = None) -> str:
    return run_device("conv_move", "fwd", duration) if duration else control_conv_move("fwd")

def stop_conveyor() -> str:
    return control_conv_move("stop")

def conveyor_hoist_up(duration: float = None) -> str:
    return run_device("conv_hoist", "fwd", duration) if duration else control_conv_hoist("fwd")

def conveyor_hoist_down(duration: float = None) -> str:
    return run_device("conv_hoist", "rev", duration) if duration else control_conv_hoist("rev")

def conveyor_hoist_stop() -> str:
    return control_conv_hoist("stop")

# —— 4. Magnet Hoist ——
def magnet_hoist_up(duration: float = None) -> str:
    return run_device("magnet_hoist", "fwd", duration) if duration else control_magnet_hoist("fwd")

def magnet_hoist_down(duration: float = None) -> str:
    return run_device("magnet_hoist", "rev", duration) if duration else control_magnet_hoist("rev")

def magnet_hoist_stop() -> str:
    return control_magnet_hoist("stop")

# —— 5. Bin-Hoist (Dumping) ——
def dumping_up(duration: float = None) -> str:
    return run_device("bin_hoist", "fwd", duration) if duration else control_bin_hoist("fwd")

def dumping_down(duration: float = None) -> str:
    return run_device("bin_hoist", "rev", duration) if duration else control_bin_hoist("rev")

def dumping_stop() -> str:
    return control_bin_hoist("stop")

def dumping(up_time: float = None, down_time: float = None) -> str:
    out = []
    if up_time is not None:
        out.append(control_bin_hoist("fwd"))
        time.sleep(up_time)
    if down_time is not None:
        out.append(control_bin_hoist("rev"))
        time.sleep(down_time)
    out.append(control_bin_hoist("stop"))
    return "\n".join(out)

# —— 6. System Macros ——
def stop_cleaning() -> str:
    return (
        stop_conveyor() + "\n" +
        conveyor_hoist_up() + "\n" +
        magnet_hoist_up()
    )

def emergency_stop() -> str:
    return "\n".join(control_device(name, "stop") for name in MOTOR_IDS)

# —— Demo / CLI ——
if __name__ == "__main__":
    method = wait_for_connection()
    print(f"[Info] Using connection method: {method.upper()}")
    print("\n>> boat_forward(2s):\n", boat_forward(2), "\n")
    print(">> boat_left():\n", boat_left(), "\n")
    print(">> boat_stop():\n", boat_stop(), "\n")
    time.sleep(1)

    print(">> dumping(up=1s, down=1s):\n", dumping(1,1), "\n")
    time.sleep(1)

    print(">> start_conveyor(3s):\n", start_conveyor(3), "\n")
    print(">> conveyor_hoist_up(2s):\n", conveyor_hoist_up(2), "\n")
    print(">> conveyor_hoist_down(1s):\n", conveyor_hoist_down(1), "\n")
    print(">> conveyor_hoist_stop():\n", conveyor_hoist_stop(), "\n")
    time.sleep(1)

    print(">> magnet_hoist_up(1s):\n", magnet_hoist_up(1), "\n")
    print(">> magnet_hoist_stop():\n", magnet_hoist_stop(), "\n")
    time.sleep(1)

    print(">> stop_cleaning():\n", stop_cleaning(), "\n")
    print(">> emergency_stop():\n", emergency_stop(), "\n")