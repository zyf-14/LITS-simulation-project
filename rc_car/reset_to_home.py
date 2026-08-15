# === reset_to_home.py ===
# Recovery script for the monitoring page's "New Cycle" button when the last
# entry attempt was denied (vehicle already inside) - the car is presumed to
# be sitting at/near trigger1, having stopped there after track_run.py's
# wait_for_gate_open() timed out. Reverses straight back to trigger3/HOME and
# stops - does not touch the gate or drive forward again, purely a physical
# position recovery so the next "New Cycle" press can start a full run from
# HOME. Reuses track_run.py's reverse_until_nth_trigger (same braking/duty
# tuning) rather than duplicating it - only 1 crossing needed here since
# trigger3 is the very next line behind trigger1 (no trigger2 in between).

import urllib.request

import motor
import sensor
from track_run import reverse_until_nth_trigger

TERMINAL_PI_RESET_COMPLETE_URL = "http://192.168.1.15/reset_complete.php"


def notify_reset_complete():
    try:
        urllib.request.urlopen(TERMINAL_PI_RESET_COMPLETE_URL, timeout=3)
        print("[RESET] Notified terminal Pi reset is complete.")
    except Exception as e:
        print(f"[RESET] Failed to notify terminal Pi of reset completion: {e}")


def main():
    sensor.setup()
    motor.setup_servo()
    print("[INFO] Reset to HOME starting - reversing until trigger3.")
    try:
        reverse_until_nth_trigger(1, "Trigger 3 (HOME)")
        notify_reset_complete()
        print("\n[DONE] Back at HOME, awaiting new cycle.")
    except KeyboardInterrupt:
        print("\n[INFO] Aborted manually.")
    finally:
        motor.stop()
        sensor.cleanup()
        print("[INFO] Cleaned up GPIO - goodbye!")


if __name__ == "__main__":
    main()
