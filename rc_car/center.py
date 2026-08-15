# === test_servo_center.py ===
from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory
from time import sleep

SERVO_PIN = 18

factory = PiGPIOFactory()
servo = Servo(SERVO_PIN, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000, pin_factory=factory)

print("[TEST] Setting servo to 90° (center)")
servo.value = 0  # 0 corresponds to 90°

try:
    while True:
        print("[LOOP] Servo at 90°")
        sleep(1)

except KeyboardInterrupt:
    print("\n[TEST] Stopped")
