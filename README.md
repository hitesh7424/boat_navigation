# 🚤 Autonomous Boat Navigation System

Modular navigation and control architecture for a Raspberry Pi + ESP32-powered waste-collecting boat.

## Modules

| Module               | Description                                 |
|----------------------|---------------------------------------------|
| `navigation_server`  | Central REST server that computes direction |
| `pondbot_motor_control` | Non-blocking motor control for ESP32       |
| `waste_detector`     | Color-based waste detection via camera      |
| `ultrasonic_host`    | Hosts 5-sensor distance data                |
| `video_host`         | Streams MJPEG camera feed                   |
| `video_recorder`     | Records 5-min segments of processed feed    |
| `gps_host`, `compass_host` | Position and heading sensors           |

## API Endpoints

- `/navigate` → from `navigation_server.py`
- `/processed_video` → from `waste_detector.py`
- `/status`, `/distance`, `/heading`, `/location`, etc.

## Setup

- Install requirements: `pip install -r requirements.txt`
- Run modules individually or orchestrate with `systemctl`, `pm2`, or Docker

## Roadmap

- [x] Sensor and navigation integration
- [ ] Vision fallback navigation
- [ ] Return-to-home coordination
- [ ] Emergency handling and mission logging
