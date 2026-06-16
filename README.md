# LITS Simulation Project

![Build Status](https://github.com/zyf-14/LITS-simulation-project/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

A low-inertia transit system (LITS) built on an autonomous RC car platform. The car follows a black line on the ground using IR sensors, handles intersection triggers, and can be driven manually via keyboard. This repo contains the Raspberry Pi control software, 3D CAD models, and a PC-side video analysis tool.

---

## Folder Structure

```
LITS-simulation-project/
├── src/                  # Raspberry Pi runtime code
│   ├── main.py           # Entry point — runs the line-following loop
│   ├── motor.py          # Servo and DC motor control (GPIO + pigpio)
│   ├── sensor.py         # IR sensor reader (GPIO)
│   ├── flow.py           # Intersection / trigger phase handler
│   ├── config.py         # Vision constants and image processing helpers
│   ├── line_following.py # Frame-level line detection logic
│   ├── camera.py         # Camera interface stub
│   └── picam_trigger.py  # PiCamera2 black-line trigger detector
│
├── tools/                # Standalone calibration and debug utilities
│   ├── calibrate_servo.py    # Interactive servo angle calibration (o/l/r/q keys)
│   ├── test_servo_center.py  # Holds servo at centre position for testing
│   └── manual_drive.py       # WASD keyboard control of motor and servo
│
├── simulation/           # PC-side analysis (no Pi hardware required)
│   └── virtual_test.py   # Replay a recorded video and visualise line-following decisions
│
├── hardware/
│   └── cad/
│       ├── RC Car/           # STL files for chassis, mounts, and panels
│       ├── Boom gate/        # STL files for the boom gate assembly
│       └── Custom Motor driver PCB schematics.pdf
│
├── archive/              # Earlier experimental variants (kept for reference)
│
├── requirements.txt
└── .gitignore
```

---

## Hardware

| Component | Detail |
|---|---|
| Platform | RC car chassis with custom 3D-printed body |
| Controller | Raspberry Pi (any model with GPIO) |
| Steering | SG90 servo on GPIO 18 |
| Drive motor | DC motor via L298N-style driver (BIN1=GPIO27, BIN2=GPIO17) |
| Line sensors | 2× IR sensors (LEFT=GPIO22, RIGHT=GPIO25) |
| Camera | Raspberry Pi Camera Module (PiCamera2) |

3D CAD models are in `hardware/cad/`. The full OnShape design is at:
[View OnShape model](https://cad.onshape.com/documents/3a9c78263ff22dc350c29a50/w/96404cf1ed0ead9f22eaefd4/e/8b10ad415629b44db3a26b1b)

---

## Software Setup

### 1. Install dependencies (on the Raspberry Pi)

```bash
pip install -r requirements.txt
sudo pigpiod        # start the pigpio daemon (required at boot)
```

### 2. Run the line follower

```bash
cd src
python main.py
```

Press `Ctrl+C` to stop. GPIO is cleaned up automatically.

### 3. Manual drive (WASD keyboard)

```bash
cd tools
python manual_drive.py
# W = forward, A = left, D = right, S = stop, Ctrl+C = quit
```

### 4. Servo calibration

```bash
cd tools
python calibrate_servo.py
# o = centre, l = left, r = right, q = quit
```

---

## Simulation (PC only)

Replay a recorded run and visualise line-detection decisions frame by frame:

```bash
cd simulation
python virtual_test.py /path/to/recording.mp4
```

Press `q` to quit.

---

## How It Works

1. `sensor.py` reads two IR sensors — each returns `HIGH` on black, `LOW` on white.
2. `main.py` steers left or right depending on which sensor sees the line.
3. When **both** sensors see black (an intersection marker), `flow.py` runs a timed stop-and-turn phase sequence.
4. `motor.py` drives the DC motor with PWM bursts and controls the servo via pigpio pulse widths.

---

## License

MIT — see [LICENSE](LICENSE) for details.
