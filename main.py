# === main.py ===
"""
Updated logic with Phase 1 flow handling:
- BOTH BLACK → delegate to flow.handle_both_black()
"""

import time
from time import time as now
import sensor
import motor
import flow

WHITE_HOLD_TO_ALIGN = 0
PRINT_INTERVAL      = 0.7
LOOP_DELAY          = 0.05

sensor.setup()
motor.setup_servo()
print("[INFO] Line following running – Ctrl-C to stop")

white_start_ts = None
last_print_ts  = 0


try:
    while True:
        left, right = sensor.read()
        now_ts = now()

        # === Phase-based BLACK-BLACK handler ===
        if left and right:
            if now_ts < flow.ignore_sensors_until:
                print("[INFO] Ignoring BOTH-BLACK during timed movement.")
                continue
            flow.handle_both_black()
            continue

        # === Realign if both white for 0.5s
        if not left and not right:
            if white_start_ts is None:
                white_start_ts = now_ts
            elif now_ts - white_start_ts >= WHITE_HOLD_TO_ALIGN:
                motor.set_servo_angle(motor.ANGLE_CENTER)
                print("[STATE] BOTH WHITE (held) → REALIGN")
        else:
            white_start_ts = None  # Reset timer

        # === Steering Logic
        if left and not right:
            motor.set_servo_angle(motor.ANGLE_LEFT)
            print("[STEER] Left=BLACK → ADJUST RIGHT")
        elif right and not left:
            motor.set_servo_angle(motor.ANGLE_RIGHT)
            print("[STEER] Right=BLACK → ADJUST LEFT")

        # === Move forward unless stopped
        motor.forward()

        # === Debug print
        if now_ts - last_print_ts >= PRINT_INTERVAL:
            print(f"Left: {'BLACK' if left else 'WHITE'} | Right: {'BLACK' if right else 'WHITE'}")
            last_print_ts = now_ts

        time.sleep(LOOP_DELAY)

except KeyboardInterrupt:
    print("\n[INFO] Stopped manually")

finally:
    motor.stop()
    sensor.cleanup()
    print("[INFO] Cleaned up GPIO – goodbye!")
