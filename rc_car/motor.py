# === motor.py ===
import RPi.GPIO as GPIO
import pigpio
from time import sleep, time

# Pins
SERVO_PIN = 18
BIN1, BIN2 = 27, 17

# Servo Angles (origin set to 100 degrees)
ANGLE_LEFT   = 93
ANGLE_CENTER = 100
ANGLE_RIGHT  = 107

# PWM + Timings
PWM_DUTY         = 11
REVERSE_PWM_DUTY = 12  # was 16 - too fast: overshot trigger3 on reverse, and lingered/
                       # re-triggered the entry sensor at trigger1 long enough to stall
                       # the ESP32's deferred "vehicle left" notify for ~2 minutes
BURST_TIME       = 0.17
STEER_TIME       = 0.1

# One short high-power pulse at the start of a movement, to break static
# friction, before dropping to the gentler steady-state PWM_DUTY above.
KICKSTART_DUTY = 25
KICKSTART_TIME = 0.1

# Brief both-pins-HIGH pulse when a stop_condition fires mid-burst, instead of
# just cutting power to coast. Coasting let the car overshoot trigger lines on
# stop (worst on reverse, which runs at higher duty/momentum) since inertia
# kept carrying it forward after power was cut - this actively kills that
# momentum right at the trigger instead of relying on friction to do it.
BRAKE_PULSE_S = 0.15  # was 0.05 - still overshot trigger3 on reverse even with the
                      # brake pulse and reduced duty, so strengthening the brake itself

DEBUG = False

# pigpio interface
pi = pigpio.pi()

def angle_to_pulse(angle):
    """
    Converts a servo angle (0–180) to pulse width in microseconds.
    0° → 500µs, 180° → 2500µs
    """
    return int(500 + (angle / 180.0) * 2000)

def setup_servo():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    for pin in (BIN1, BIN2):
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    set_servo_angle(ANGLE_CENTER)
    if DEBUG:
        print(f"[SETUP] Servo centered at {ANGLE_CENTER}°")

def set_servo_angle(angle):
    pulse = angle_to_pulse(angle)
    pi.set_servo_pulsewidth(SERVO_PIN, pulse)
    if DEBUG:
        print(f"[STEER] Set to {angle}° (pulse={pulse}µs)")

def _pwm_burst(pin_high, pin_low, duty, duration=BURST_TIME, freq=100, stop_condition=None, on_tick=None):
    """Runs a software-PWM burst for up to `duration` seconds.

    on_tick, if given, is called every sub-cycle (~1/freq seconds) purely for
    side effects (e.g. reading sensors and adjusting steering) - it does NOT
    stop the burst. Without this, a caller driving via repeated forward()
    calls only gets to see sensor state BETWEEN bursts, never during one -
    a real blind window (BURST_TIME long) where a brief line could pass
    under the sensor without ever being sampled.

    stop_condition, if given, is polled every sub-cycle too, and the burst
    cuts power and returns True the instant it's true, rather than the caller
    only finding out after the full duration elapses.

    Returns False if the burst ran its full duration without stop_condition
    ever firing (or if none was given)."""
    period = 1.0 / freq
    on_time  = period * duty / 100.0
    off_time = period - on_time
    t0 = time()
    while time() - t0 < duration:
        if on_tick is not None:
            on_tick()
        if stop_condition is not None and stop_condition():
            GPIO.output(pin_high, GPIO.HIGH)
            GPIO.output(pin_low,  GPIO.HIGH)
            sleep(BRAKE_PULSE_S)
            GPIO.output(pin_high, GPIO.LOW)
            GPIO.output(pin_low,  GPIO.LOW)
            return True
        GPIO.output(pin_high, GPIO.HIGH)
        GPIO.output(pin_low,  GPIO.LOW)
        sleep(on_time)
        GPIO.output(pin_high, GPIO.LOW)
        GPIO.output(pin_low,  GPIO.LOW)
        sleep(off_time)
    return False

def forward(stop_condition=None, on_tick=None):
    return _pwm_burst(BIN1, BIN2, PWM_DUTY, stop_condition=stop_condition, on_tick=on_tick)

def reverse(stop_condition=None, on_tick=None):
    return _pwm_burst(BIN2, BIN1, REVERSE_PWM_DUTY, stop_condition=stop_condition, on_tick=on_tick)

def kickstart_forward(stop_condition=None, on_tick=None):
    """One short burst at KICKSTART_DUTY to break static friction before the
    caller settles into steady-state forward() calls. Accepts stop_condition
    and on_tick like forward() does, so a trigger-detecting/steering caller
    doesn't get a blind window during the kickstart pulse either."""
    return _pwm_burst(BIN1, BIN2, KICKSTART_DUTY, duration=KICKSTART_TIME, stop_condition=stop_condition, on_tick=on_tick)

def kickstart_reverse(stop_condition=None, on_tick=None):
    """Same as kickstart_forward(), reverse direction."""
    return _pwm_burst(BIN2, BIN1, KICKSTART_DUTY, duration=KICKSTART_TIME, stop_condition=stop_condition, on_tick=on_tick)

def stop():
    for pin in (BIN1, BIN2):
        GPIO.output(pin, GPIO.LOW)
    set_servo_angle(ANGLE_CENTER)
    pi.set_servo_pulsewidth(SERVO_PIN, 0)  # Stop sending signal (release servo)
    if DEBUG:
        print("[SHUTDOWN] Servo released")
