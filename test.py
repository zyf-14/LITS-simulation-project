# servo_test.py
import time
import pigpio

SERVO_PIN = 18  # Adjust as needed

pi = pigpio.pi()
if not pi.connected:
    exit()

try:
    print("Setting servo to 90°")
    pi.set_servo_pulsewidth(SERVO_PIN, 1500)  # 90° (middle)
    time.sleep(5)

finally:
    print("Releasing servo...")
    pi.set_servo_pulsewidth(SERVO_PIN, 0)  # Release
    pi.stop()
