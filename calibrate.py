# === servo_calibrate.py ===
import time
import pigpio
import sys
import termios
import tty

SERVO_GPIO = 18  # Change if you're using a different GPIO pin
ORIGIN = 100
LEFT = 90
RIGHT = 110

# Convert angle to pulse width
def angle_to_pulse(angle):
    return int(500 + (angle / 180.0) * 2000)

# Read a single key press from terminal
def read_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

# Initialize pigpio
pi = pigpio.pi()
if not pi.connected:
    print("Failed to connect to pigpio daemon.")
    sys.exit()

print("Calibrating SG90 Servo. Press:")
print("  o → Origin (90°)")
print("  l → Left   (80°)")
print("  r → Right  (100°)")
print("  q → Quit\n")

try:
    while True:
        key = read_key().lower()
        if key == 'o':
            pulse = angle_to_pulse(ORIGIN)
            pi.set_servo_pulsewidth(SERVO_GPIO, pulse)
            print("[STEER] Set to 90°")
        elif key == 'l':
            pulse = angle_to_pulse(LEFT)
            pi.set_servo_pulsewidth(SERVO_GPIO, pulse)
            print("[STEER] Set to 80°")
        elif key == 'r':
            pulse = angle_to_pulse(RIGHT)
            pi.set_servo_pulsewidth(SERVO_GPIO, pulse)
            print("[STEER] Set to 100°")
        elif key == 'q':
            break
finally:
    pi.set_servo_pulsewidth(SERVO_GPIO, 0)  # Release the servo
    pi.stop()
    print("\nServo released. Exiting.")
