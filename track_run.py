# === track_run.py ===
# Single-cycle track test run, now integrated with the real boom gate. The
# ESP32's entry ultrasonic sensor is physically co-located with trigger1, and
# its exit sensor sits somewhere between trigger1 and trigger2 - so the real
# LPR/gate pipeline fires from the actual hardware as the car drives the
# track, this script just waits on / requests the right things at the right
# points. Does NOT modify main.py/flow.py - reuses motor.py/sensor.py like
# checkpoint_run.py (which this file's ESP32 HTTP helpers are ported from).
#
# Track layout (75cm straight track, start wall -> end wall):
#   [START WALL] -- trigger3 (HOME) -- trigger1 (gate) -- trigger2 (wall approach) -- [END WALL]
#
# Flow:
#   1. Ready: vehicle must already be sitting on trigger3 (HOME) - both sensors black.
#   2. Drive forward -> trigger1 -> stop, wait for the REAL gate to open on its
#      own (the co-located entry sensor + terminal-Pi LPR pipeline fire from
#      the hardware - this just polls /status, no HTTP call needed here).
#   3. Drive forward -> trigger2. Along the way the car also clears the ESP32's
#      exit sensor, which auto-closes the gate for real (production behavior -
#      CLOSE_ON_ENTRY_CLEAR is off). Stop at trigger2, wait a fixed
#      WAIT_AT_TRIGGER2_S, then keep driving 1 more second (nosing into the
#      end wall) -> stop.
#   4. Tell the ESP32 directly to reopen the gate for the return pass (bypasses
#      the terminal-Pi/LPR bridge, same as checkpoint_run.py's CP2) and wait
#      for confirmation.
#   5. Reverse straight back. The line sensors can't tell trigger1/trigger2/
#      trigger3's lines apart - all just read "both black" - so this counts
#      crossings instead. The reverse leg starts just past trigger2 (from the
#      nose-into-end-wall step), so the first line it re-crosses is trigger2's
#      own line: 1st crossing (trigger2) is ignored, 2nd crossing (trigger1)
#      is ignored, 3rd crossing (trigger3/HOME) stops.
#   6. Tell the ESP32 directly to close the gate, wait for confirmation (warns
#      but doesn't abort on timeout - the cycle is basically done by then).
#   7. Continue reversing an additional FIXED 5s past HOME (confirmed clear
#      behind it).
#   8. Drive forward again until HOME/trigger3 is detected once more -> stop.
#      Cycle complete, script exits (single-shot - rerun for another cycle).
#
# Forward legs use the same auto line-correction logic ported from main.py:
# continuously read the sensors (inside the motor burst, not just between
# bursts) and hold any left/right correction for CORRECTION_HOLD_S before
# re-evaluating. Reverse legs deliberately do NOT use this - the front-mounted
# line sensors trail behind the car in reverse, so steering doesn't help there
# (same reasoning checkpoint_run.py already used for its reverse leg).

import json
import time
import urllib.request
from time import time as now

import motor
import sensor

ESP32_BASE = "http://192.168.15.250"
TERMINAL_PI_RESET_COMPLETE_URL = "http://192.168.1.15/reset_complete.php"

WAIT_AT_TRIGGER2_S    = 3
DRIVE_INTO_WALL_S     = 1
REVERSE_PAST_HOME_S   = 3
CORRECTION_HOLD_S     = 0.2  # ported from main.py's auto line-correction
LOOP_DELAY            = 0.02  # tightened from 0.05 - at low torque the car can stick then
                              # suddenly lurch forward, and a coarser poll interval risks
                              # jumping past a trigger line between samples without ever
                              # reading it as black

CP1_GATE_TIMEOUT      = 60  # real LPR pipeline can take a while (camera OCR etc.)
CP2_GATE_TIMEOUT      = 15  # direct ESP32 command, should be near-instant
CLOSE_CONFIRM_TIMEOUT = 15  # exit sensor has been flaky before - warn, don't abort, on timeout


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


CLOSE_RETRY_INTERVAL_S = 3  # re-send /close_gate this often while waiting

def wait_for_gate_close(timeout):
    """Polls for the gate closing, periodically re-sending /close_gate rather
    than firing it once and hoping. A single close request can get silently
    deferred by the ESP32's presence interlock (taskBoomgate refuses to move
    the servo while vehicle_at_entry/vehicle_at_exit reads true) if the car's
    own body is still triggering a sensor at that exact moment mid-reverse -
    confirmed live: gate stayed open for the rest of a "successful" cycle
    because the one-shot close request landed during exactly that window and
    nothing ever asked again. Retrying covers that instead of requiring a
    manual close afterward."""
    print(f"[WAIT] Confirming gate closes (up to {timeout}s)...")
    start = now()
    last_retry = start
    while now() - start < timeout:
        if not gate_is_open():
            print("[WAIT] Gate confirmed closed.")
            return True
        if now() - last_retry >= CLOSE_RETRY_INTERVAL_S:
            request_gate_close()
            last_retry = now()
        time.sleep(1.0)
    print("[WAIT] Gate close not confirmed within timeout.")
    return False


def notify_confirmed_home():
    """Tells the terminal Pi the car is confirmed back at HOME, clearing
    latest_attempt.json - without this, the reverse leg's own pass back over
    the entry sensor (which re-arms OCR now that demo_trigger.php no longer
    blocks) can log a spurious DENIED entry attempt for the same car finishing
    its own lap, which would otherwise make the monitoring page's "New Cycle"
    button think a reset-to-HOME is still needed even though the car already
    completed a full, successful round trip."""
    try:
        urllib.request.urlopen(TERMINAL_PI_RESET_COMPLETE_URL, timeout=3)
        print("[HOME] Notified terminal Pi vehicle is confirmed back at HOME.")
    except Exception as e:
        print(f"[HOME] Failed to notify terminal Pi: {e}")


def both_black():
    left, right = sensor.read()
    return left and right


STEER_ONSET_DEBOUNCE_S = 0.08  # a new left/right correction must be seen for this long
                                # before it's actually committed. Without this, approaching
                                # a trigger line at a slight angle makes one sensor read
                                # black a beat before the other - on_tick saw that as real
                                # drift and steered, then both-black fired a moment later
                                # and stopped the car mid-turn (visible spurious veer right
                                # at trigger2). Genuine drift persists well past this window;
                                # a trigger-crossing blip doesn't.


def make_steer_on_tick():
    """Builds an on_tick callback for motor.forward()/kickstart_forward() that
    continuously corrects steering left/right based on which sensor reads
    black, holding each correction for CORRECTION_HOLD_S before re-evaluating -
    ported directly from main.py's auto line-correction logic. A new turn must
    also be seen for STEER_ONSET_DEBOUNCE_S before it's committed (see above)."""
    state = {
        "correction_until": 0.0,
        "current_angle": motor.ANGLE_CENTER,
        "pending_desired": None,
        "pending_since": 0.0,
    }

    def on_tick():
        left, right = sensor.read()
        now_ts = time.time()
        if now_ts < state["correction_until"]:
            return
        if left and not right:
            desired = motor.ANGLE_LEFT
        elif right and not left:
            desired = motor.ANGLE_RIGHT
        else:
            desired = motor.ANGLE_CENTER

        if desired == motor.ANGLE_CENTER:
            state["pending_desired"] = None
            if desired != state["current_angle"]:
                motor.set_servo_angle(desired)
                state["current_angle"] = desired
            return

        if state["pending_desired"] != desired:
            state["pending_desired"] = desired
            state["pending_since"] = now_ts
            return
        if now_ts - state["pending_since"] < STEER_ONSET_DEBOUNCE_S:
            return

        if desired != state["current_angle"]:
            motor.set_servo_angle(desired)
            state["current_angle"] = desired
            state["correction_until"] = now_ts + CORRECTION_HOLD_S

    return on_tick


def drive_forward_until_trigger(label):
    """Drive forward until a NEW both-black trigger is detected. Requires
    leaving the current line (a non-black reading) at least once first, so
    starting from on top of a line - a real case, since the vehicle begins
    sitting on trigger3/HOME - doesn't count as an instant trigger.

    The sensor is polled from INSIDE each motor burst (every ~10ms sub-cycle,
    via motor.py's stop_condition), not just between bursts - otherwise the
    car is blind to the line for the whole burst duration and can coast right
    over a narrow line without ever sampling it while on top of it."""
    print(f"[DRIVE] Forward -> {label}")
    state = {"armed": not both_black()}  # if already on a line, must leave it before it counts

    def should_stop():
        if both_black():
            return state["armed"]
        state["armed"] = True
        return False

    steer_on_tick = make_steer_on_tick()

    motor.set_servo_angle(motor.ANGLE_CENTER)
    if motor.kickstart_forward(stop_condition=should_stop, on_tick=steer_on_tick):
        motor.stop()
        print(f"[TRIGGER] {label} detected.")
        return
    while True:
        hit = motor.forward(stop_condition=should_stop, on_tick=steer_on_tick)
        if hit:
            motor.stop()
            print(f"[TRIGGER] {label} detected.")
            return
        time.sleep(LOOP_DELAY)


def drive_forward_for(seconds, label):
    print(f"[DRIVE] Forward for {seconds}s -> {label}")
    steer_on_tick = make_steer_on_tick()
    motor.set_servo_angle(motor.ANGLE_CENTER)
    motor.kickstart_forward(on_tick=steer_on_tick)
    t0 = time.time()
    while time.time() - t0 < seconds:
        motor.forward(on_tick=steer_on_tick)
        time.sleep(LOOP_DELAY)
    motor.stop()
    print(f"[DRIVE] {label} complete.")


def reverse_until_nth_trigger(n, label):
    """Reverse straight back until a both-black line has been crossed n times.
    Same leave-the-line debounce as drive_forward_until_trigger, applied per
    crossing so sitting on top of a line doesn't get counted repeatedly. Same
    inside-the-burst sensor polling too - a missed crossing here is exactly
    the "LED saw black but the car kept reversing" failure this was built to
    fix.

    Note for the HOME leg: the car starts this leg just past trigger2 (having
    nosed further into the end wall after stopping there), so the crossing
    count must include trigger2's own line, not just trigger1/trigger3."""
    print(f"[DRIVE] Reverse -> {label} (crossing #{n})")
    state = {"armed": not both_black(), "crossings": 0}

    def should_stop():
        if both_black():
            if state["armed"]:
                state["crossings"] += 1
                state["armed"] = False
                print(f"[TRIGGER] Reverse crossing #{state['crossings']} detected.")
                if state["crossings"] >= n:
                    return True
            return False
        state["armed"] = True
        return False

    motor.set_servo_angle(motor.ANGLE_CENTER)
    if motor.kickstart_reverse(stop_condition=should_stop):
        motor.stop()
        print(f"[TRIGGER] {label} reached.")
        return
    while True:
        hit = motor.reverse(stop_condition=should_stop)
        if hit:
            motor.stop()
            print(f"[TRIGGER] {label} reached.")
            return
        time.sleep(LOOP_DELAY)


def reverse_for(seconds, label):
    print(f"[DRIVE] Reverse for {seconds}s -> {label}")
    motor.set_servo_angle(motor.ANGLE_CENTER)
    motor.kickstart_reverse()
    t0 = time.time()
    while time.time() - t0 < seconds:
        motor.reverse()
        time.sleep(LOOP_DELAY)
    motor.stop()
    print(f"[DRIVE] {label} complete.")


def main():
    sensor.setup()
    motor.setup_servo()
    print("[INFO] Track run starting (PWM_DUTY={}%, BURST_TIME={}s) - Ctrl-C to abort."
          .format(motor.PWM_DUTY, motor.BURST_TIME))
    print("[INFO] Vehicle must already be sitting on trigger3 (HOME) to begin.\n")

    try:
        # --- trigger3 (HOME) -> trigger1: stop, wait for the REAL gate to open ---
        drive_forward_until_trigger("Trigger 1 (gate)")
        if not wait_for_gate_open(CP1_GATE_TIMEOUT):
            print("[ABORT] Gate never opened at trigger1 - stopping run.")
            return

        # --- trigger1 -> trigger2: stop, wait fixed 3s, then nose into the end wall ---
        # (the exit sensor should auto-close the real gate for real somewhere along
        # this leg - production behavior, CLOSE_ON_ENTRY_CLEAR is off)
        drive_forward_until_trigger("Trigger 2 (wall approach)")
        time.sleep(WAIT_AT_TRIGGER2_S)
        drive_forward_for(DRIVE_INTO_WALL_S, "Nose into end wall")

        # --- trigger2: tell the ESP32 directly to reopen the gate for the return pass ---
        print("[CP2] Notifying ESP32 directly to reopen for the return pass.")
        request_gate_open()
        if not wait_for_gate_open(CP2_GATE_TIMEOUT):
            print("[ABORT] Gate never reopened at trigger2 - stopping run.")
            return

        # --- reverse: ignore trigger2 (1st crossing) and trigger1 (2nd), stop at trigger3/HOME (3rd) ---
        reverse_until_nth_trigger(3, "Trigger 3 (HOME)")

        # --- trigger3/HOME reached on reverse: tell the ESP32 to close the gate ---
        print("[CP3] Vehicle back at HOME - requesting gate close.")
        request_gate_close()
        wait_for_gate_close(CLOSE_CONFIRM_TIMEOUT)

        # --- continue reversing an additional fixed 5s past HOME ---
        reverse_for(REVERSE_PAST_HOME_S, "Clear past HOME")

        # --- forward again until HOME/trigger3 detected once more - cycle complete ---
        drive_forward_until_trigger("Trigger 3 (HOME) - cycle complete")
        notify_confirmed_home()

        print("\n[DONE] Track run complete.")

    except KeyboardInterrupt:
        print("\n[INFO] Aborted manually.")
    finally:
        motor.stop()
        sensor.cleanup()
        print("[INFO] Cleaned up GPIO - goodbye!")


if __name__ == "__main__":
    main()
