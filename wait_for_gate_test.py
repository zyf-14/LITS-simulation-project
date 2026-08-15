# === wait_for_gate_test.py ===
"""
Standalone test: poll the terminal Pi for the boom gate's live state and drive
forward only while it's open. The RC car's camera can't see the gate itself, so
this is the network signal that replaces that visual check.

Not wired into the main line-follower yet - isolated test first.
"""

import time
import requests
import motor

GATE_STATUS_URL = "http://192.168.1.15/gate_status.php"
POLL_TIMEOUT_S = 3
CLOSED_POLL_INTERVAL_S = 0.5  # no need to hammer the endpoint while just waiting


def gate_is_open():
    try:
        r = requests.get(GATE_STATUS_URL, timeout=POLL_TIMEOUT_S)
        r.raise_for_status()
        return bool(r.json().get("gate_is_open", False))
    except Exception as e:
        print(f"[GATE] Status check failed: {e} - treating as closed")
        return False


def main():
    motor.setup_servo()
    print("[INFO] Waiting for gate to open - Ctrl-C to stop")

    was_open = False
    try:
        while True:
            open_now = gate_is_open()
            if open_now != was_open:
                print(f"[GATE] {'OPEN -> moving forward' if open_now else 'CLOSED -> stopped'}")
                was_open = open_now

            if open_now:
                motor.forward()
            else:
                motor.stop()
                time.sleep(CLOSED_POLL_INTERVAL_S)

    except KeyboardInterrupt:
        print("\n[INFO] Stopped manually")

    finally:
        motor.stop()
        print("[INFO] Cleaned up - goodbye!")


if __name__ == "__main__":
    main()
