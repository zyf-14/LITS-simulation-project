# === wasd_drive.py ===
import motor
import termios
import tty
import sys
import time

def get_key():
    """Blocking read of a single keypress (with Ctrl+C support)"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)  # <-- FIX: Ctrl+C works now
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# === Setup
motor.setup_servo()
motor.set_servo_angle(motor.ANGLE_CENTER)
print("[INFO] Ready – W/A/D to control, S to reverse, X to stop. Press Ctrl+C to exit.")

try:
    while True:
        key = get_key()

        if key == 'w':
            motor.set_servo_angle(motor.ANGLE_CENTER)
            motor.forward()
            print("[INPUT] W → ORIGIN + FORWARD")

        elif key == 'a':
            motor.set_servo_angle(motor.ANGLE_LEFT)
            motor.forward()
            print("[INPUT] A → LEFT + FORWARD")

        elif key == 'd':
            motor.set_servo_angle(motor.ANGLE_RIGHT)
            motor.forward()
            print("[INPUT] D → RIGHT + FORWARD")

        elif key == 'x':
            motor.stop()
            print("[INPUT] X → STOP")

        elif key == 's':
            motor.set_servo_angle(motor.ANGLE_CENTER)
            motor.reverse()
            print("[INPUT] S → ORIGIN + REVERSE")

except KeyboardInterrupt:
    print("\n[EXIT] Ctrl+C detected – quitting...")

finally:
    motor.stop()
    print("[INFO] Clean shutdown complete. Bye!")
