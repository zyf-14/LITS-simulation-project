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
PWM_DUTY     = 18
BURST_TIME   = 0.16
STEER_TIME   = 0.1

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

def _pwm_burst(pin_high, pin_low, duty, duration=BURST_TIME, freq=100):
    period = 1.0 / freq
    on_time  = period * duty / 100.0
    off_time = period - on_time
    t0 = time()
    while time() - t0 < duration:
        GPIO.output(pin_high, GPIO.HIGH)
        GPIO.output(pin_low,  GPIO.LOW)
        sleep(on_time)
        GPIO.output(pin_high, GPIO.LOW)
        GPIO.output(pin_low,  GPIO.LOW)
        sleep(off_time)

def forward():
    _pwm_burst(BIN1, BIN2, PWM_DUTY)

def stop():
    for pin in (BIN1, BIN2):
        GPIO.output(pin, GPIO.LOW)
    set_servo_angle(ANGLE_CENTER)
    pi.set_servo_pulsewidth(SERVO_PIN, 0)  # Stop sending signal (release servo)
    if DEBUG:
        print("[SHUTDOWN] Servo released")
