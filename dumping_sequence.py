# dumping_sequence.py
# Autonomous task handler for navigating to shore and dumping collected waste.
# This script depends on visual shoreline detection and motor control via pondbot_motor_control.py

import time
import requests
import pondbot_motor_control as motor

# Configurations
SHORE_STATUS_URL = "http://localhost:8009/shore_status"
VIDEO_FEED_URL = "http://localhost:8001/video_feed"
DETECTION_TIMEOUT = 60  # seconds to search for shore

# Step 1: Navigate to Shore using shoreline detection

def move_towards_shore():
    print("🔍 Searching for shoreline...")
    start_time = time.time()
    while time.time() - start_time < DETECTION_TIMEOUT:
        try:
            res = requests.get(SHORE_STATUS_URL, timeout=2)
            if res.status_code == 200 and res.json().get("danger"):
                print("✅ Shore detected!")
                return True
            motor.boat_forward(1, blocking=True)
        except Exception as e:
            print("⚠️ Shore detection failed, retrying...")
        time.sleep(0.5)
    print("❌ Shoreline not detected in time.")
    return False

# Step 2: Dumping sequence

def perform_dumping():
    print("♻️ Reversing and rotating before dumping...")
    motor.boat_backward(2, blocking=True)
    motor.boat_left(2, blocking=True)
    print("🚮 Executing dump...")
    motor.control_device("conv_move", "fwd")  # run conveyor briefly
    motor.run_device("bin_hoist", "fwd", 3, blocking=True)  # raise bin
    motor.run_device("bin_hoist", "rev", 3, blocking=True)  # lower bin
    motor.control_device("conv_move", "stop")

# Step 3: Resume normal operation

def resume_patrol():
    print("✅ Dump complete. Resuming patrol...")
    motor.boat_right(2, blocking=True)
    motor.boat_forward(2, blocking=True)

# Full routine entry point

def run_sequence():
    success = move_towards_shore()
    if success:
        perform_dumping()
    resume_patrol()

if __name__ == "__main__":
    run_sequence()
