# === main.py ===
"""
Auto line-correction, updated with:
- Continuous (inside-burst) sensor polling via motor.py's on_tick, instead of
  only checking between bursts - previously there was a blind window the
  length of BURST_TIME every single burst where the sensor was never read,
  letting a brief line pass under it undetected.
- A fixed CORRECTION_HOLD_S hold on any left/right steering correction before
  reverting to straight - previously steering was purely reactive every
  ~LOOP_DELAY, flipping instantly the moment a sensor reading changed.
- BOTH BLACK -> delegate to flow.handle_both_black() (unchanged from before).
"""

import time
from time import time as now
import sensor
import motor
import flow

CORRECTION_HOLD_S = 0.2
PRINT_INTERVAL     = 0.7

sensor.setup()
motor.setup_servo()
print("[INFO] Line following running - Ctrl-C to stop")

state = {
    "correction_until": 0.0,
    "current_angle": motor.ANGLE_CENTER,
    "last_print_ts": 0.0,
}


def steer_on_tick():
    """Runs every ~10ms sub-cycle from inside the motor burst (see
    motor._pwm_burst's on_tick). Continuously reads the sensors and updates
    steering, but once a left/right correction starts it's held for
    CORRECTION_HOLD_S before being re-evaluated, rather than re-decided every
    single tick."""
    left, right = sensor.read()
    now_ts = time.time()

    if now_ts - state["last_print_ts"] >= PRINT_INTERVAL:
        print(f"Left: {'BLACK' if left else 'WHITE'} | Right: {'BLACK' if right else 'WHITE'}")
        state["last_print_ts"] = now_ts

    if left and right:
        return  # both-black is handled by the outer loop via stop_condition, not here

    if now_ts < state["correction_until"]:
        return  # still holding the current correction, don't re-evaluate yet

    if left and not right:
        desired = motor.ANGLE_LEFT
    elif right and not left:
        desired = motor.ANGLE_RIGHT
    else:
        desired = motor.ANGLE_CENTER

    if desired != state["current_angle"]:
        motor.set_servo_angle(desired)
        state["current_angle"] = desired
        if desired != motor.ANGLE_CENTER:
            state["correction_until"] = now_ts + CORRECTION_HOLD_S
        holding = " (holding {}s)".format(CORRECTION_HOLD_S) if desired != motor.ANGLE_CENTER else " (straight)"
        print(f"[STEER] -> {desired}°{holding}")


def both_black_stop():
    left, right = sensor.read()
    if left and right:
        return now() >= flow.ignore_sensors_until
    return False


try:
    while True:
        hit = motor.forward(stop_condition=both_black_stop, on_tick=steer_on_tick)
        if hit:
            flow.handle_both_black()
            continue
        time.sleep(0.01)

except KeyboardInterrupt:
    print("\n[INFO] Stopped manually")

finally:
    motor.stop()
    sensor.cleanup()
    print("[INFO] Cleaned up GPIO - goodbye!")
