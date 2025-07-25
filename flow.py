# === flow.py ===

import time
import motor
import sensor
import camera  # Future use
import threading

trigger_phase = 0
### ignore_sensors_until = 1

def handle_both_black():
    global trigger_phase

    if trigger_phase == 0:
        print("[PHASE A] Stopping, setting servo to 100°")
        motor.stop()
        motor.set_servo_angle(100)
        time.sleep(1.0)
        print("[PHASE A] Done. Awaiting phase B.")
        trigger_phase = 1
