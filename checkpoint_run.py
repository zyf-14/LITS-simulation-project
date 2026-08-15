# === checkpoint_run.py ===
# Multi-checkpoint boom-gate demo run. Does NOT modify main.py or flow.py -
# the plain line-following program stays exactly as-is; this is a separate
# entry point reusing the same motor.py / sensor.py modules.
#
# Flow:
#   CP1 (entry, before gate)  -> stop, wait for the real LPR pipeline to open
#                                 the gate on its own (ESP32's entry sensor +
#                                 terminal-Pi LPR should fire naturally here)
#   CP2 (past the gate)       -> stop, tell the ESP32 directly to reopen the
#                                 gate for the return pass, wait for it to open
#   reverse to CP3            -> back out past the gate
#   CP3 (clear of gate)       -> tell the ESP32 to close the gate, done
#
# "Checkpoint" = both line sensors reading BLACK at once (a perpendicular
# marker line), same trigger flow.py's handle_both_black() uses for its
# Phase A stop - just extended here into a full multi-stage run.
#
# Talks to the ESP32 directly (not through the terminal Pi) for the CP2
# reopen / CP3 close calls: the ESP32 already exposes /open_gate and
# /close_gate for exactly this, and it decouples this run from the
# terminal-Pi/LPR5Lite bridge (which is a separate, currently flaky, piece).

import json
import time
import urllib.request
from time import time as now

import motor
import sensor

ESP32_BASE = "http://192.168.15.250"

# Lower/gentler than motor.py's shared defaults (used by main.py) - overriding
# the module attributes here only affects THIS process, main.py on disk is
# untouched. Start conservative; tune upward if the car struggles to move.
motor.PWM_DUTY = 15
motor.BURST_TIME = 0.15

LOOP_DELAY = 0.05
CP1_GATE_TIMEOUT = 60   # real LPR pipeline can take a while (camera OCR etc.)
CP2_GATE_TIMEOUT = 15   # direct ESP32 command, should be near-instant
CLOSE_CONFIRM_TIMEOUT = 10


def _http_get(path, timeout=3):
    with urllib.request.urlopen(f"{ESP32_BASE}{path}", timeout=timeout) as resp:
        return resp.status, resp.read().decode()


def esp32_status():
    try:
        _, body = _http_get("/status")
        return json.loads(body)
    except Exception as e:
        print(f"[ESP32] status check failed: {e}")
        return None


def gate_is_open():
    status = esp32_status()
    return bool(status and status.get("gate_is_open"))


def request_gate_open():
    try:
        code, body = _http_get("/open_gate")
        print(f"[ESP32] open_gate -> {code}: {body.strip()}")
    except Exception as e:
        print(f"[ESP32] open_gate call failed: {e}")


def request_gate_close():
    try:
        code, body = _http_get("/close_gate")
        print(f"[ESP32] close_gate -> {code}: {body.strip()}")
    except Exception as e:
        print(f"[ESP32] close_gate call failed: {e}")


def wait_for_gate_open(timeout):
    print(f"[WAIT] Waiting up to {timeout}s for gate to open...")
    start = now()
    while now() - start < timeout:
        if gate_is_open():
            print("[WAIT] Gate is open.")
            return True
        time.sleep(1.0)
    print("[WAIT] Timed out waiting for gate to open.")
    return False


def wait_for_gate_close(timeout):
    print(f"[WAIT] Confirming gate closes (up to {timeout}s)...")
    start = now()
    while now() - start < timeout:
        if not gate_is_open():
            print("[WAIT] Gate confirmed closed.")
            return True
        time.sleep(1.0)
    print("[WAIT] Gate close not confirmed within timeout.")
    return False


def drive_forward_to_checkpoint(label):
    """Line-follow forward (same steering logic as main.py) until a both-black marker is hit."""
    print(f"[DRIVE] Forward -> {label}")
    while True:
        left, right = sensor.read()

        if left and right:
            motor.stop()
            print(f"[CHECKPOINT] Reached {label}.")
            return

        if not left and not right:
            motor.set_servo_angle(motor.ANGLE_CENTER)
        elif left and not right:
            motor.set_servo_angle(motor.ANGLE_LEFT)
        elif right and not left:
            motor.set_servo_angle(motor.ANGLE_RIGHT)

        motor.forward()
        time.sleep(LOOP_DELAY)


def drive_reverse_to_checkpoint(label):
    """Reverse straight (servo centered) until a both-black marker is hit.

    Front-mounted line sensors trail behind the car in reverse, so they
    can't usefully steer here - only used to detect the checkpoint marker.
    """
    print(f"[DRIVE] Reverse -> {label}")
    motor.set_servo_angle(motor.ANGLE_CENTER)
    while True:
        left, right = sensor.read()

        if left and right:
            motor.stop()
            print(f"[CHECKPOINT] Reached {label}.")
            return

        motor.reverse()
        time.sleep(LOOP_DELAY)


def main():
    sensor.setup()
    motor.setup_servo()
    print("[INFO] Checkpoint run starting (PWM_DUTY={}%, BURST_TIME={}s) - Ctrl-C to abort.\n"
          .format(motor.PWM_DUTY, motor.BURST_TIME))

    try:
        # --- CP1: drive to entry, stop, wait for the real LPR pipeline ---
        drive_forward_to_checkpoint("Checkpoint 1 (entry)")
        if not wait_for_gate_open(CP1_GATE_TIMEOUT):
            print("[ABORT] Gate never opened at checkpoint 1 - stopping run.")
            return

        # --- CP1 -> CP2: proceed through the open gate ---
        drive_forward_to_checkpoint("Checkpoint 2 (past gate)")

        # --- CP2: request the gate reopen for the return pass ---
        print("[CP2] Notifying ESP32 directly to reopen for the return pass.")
        request_gate_open()
        if not wait_for_gate_open(CP2_GATE_TIMEOUT):
            print("[ABORT] Gate never reopened at checkpoint 2 - stopping run.")
            return

        # --- CP2 -> CP3: reverse back out past the gate ---
        drive_reverse_to_checkpoint("Checkpoint 3 (clear of gate)")

        # --- CP3: confirm clear, close the gate ---
        print("[CP3] Vehicle clear - requesting gate close.")
        request_gate_close()
        wait_for_gate_close(CLOSE_CONFIRM_TIMEOUT)

        print("\n[DONE] Checkpoint run complete.")

    except KeyboardInterrupt:
        print("\n[INFO] Aborted manually.")
    finally:
        motor.stop()
        sensor.cleanup()
        print("[INFO] Cleaned up GPIO - goodbye!")


if __name__ == "__main__":
    main()
