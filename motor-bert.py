# === motor.py ===
import RPi.GPIO as GPIO
import pigpio
from time import sleep, time
import threading

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


class MotorController(threading.Thread):
    def __init__(self):
        super().__init__()
        self.pi = pigpio.pi()
        self.running = False
        self.forward_request = False
        self.forward_duration = BURST_TIME
        self.lock = threading.Lock()

        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for pin in (BIN1, BIN2):
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

        # Center steering
        self.set_servo_angle(ANGLE_CENTER)
        if DEBUG:
            print(f"[SETUP] Servo centered at {ANGLE_CENTER}°")

    def angle_to_pulse(self, angle):
        return int(500 + (angle / 180.0) * 2000)

    def set_servo_angle(self, angle):
        pulse = self.angle_to_pulse(angle)
        self.pi.set_servo_pulsewidth(SERVO_PIN, pulse)
        if DEBUG:
            print(f"[STEER] Set to {angle}° (pulse={pulse}µs)")

    def forward(self, duration=BURST_TIME):
        with self.lock:
            self.forward_request = True
            self.forward_duration = duration

    def stop(self):
        with self.lock:
            self.forward_request = False
        for pin in (BIN1, BIN2):
            GPIO.output(pin, GPIO.LOW)
        self.set_servo_angle(ANGLE_CENTER)
        self.pi.set_servo_pulsewidth(SERVO_PIN, 0)
        if DEBUG:
            print("[SHUTDOWN] Servo released")

    def steer_left(self):
        self.set_servo_angle(ANGLE_LEFT)

    def steer_right(self):
        self.set_servo_angle(ANGLE_RIGHT)

    def steer_center(self):
        self.set_servo_angle(ANGLE_CENTER)

    def run(self):
        self.running = True
        while self.running:
            with self.lock:
                if self.forward_request:
                    self._pwm_burst(BIN1, BIN2, PWM_DUTY, self.forward_duration)
                    self.forward_request = False
            sleep(0.01)

    def _pwm_burst(self, pin_high, pin_low, duty, duration=BURST_TIME, freq=100):
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

    def shutdown(self):
        self.running = False
        self.stop()
        self.join()


# === Example Usage ===
if __name__ == "__main__":
    motor = MotorController()
    motor.start()

    try:
        print("Moving forward and steering right...")
        motor.forward(1)
        motor.steer_right()
        sleep(0.5)
        motor.steer_left()
        sleep(0.5)
        motor.steer_center()

    finally:
        print("Stopping motor...")
        motor.shutdown()
        GPIO.cleanup()

