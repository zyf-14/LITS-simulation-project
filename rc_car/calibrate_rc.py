# === calibrate_rc.py ===
# Combined calibration for rear motor, line sensors, and steering servo.
# Reuses motor.py / sensor.py directly (the same modules main.py drives)
# so calibration exercises the exact final-version code, not a copy.

import sys
import termios
import tty
from time import sleep

import motor
import sensor


def read_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def print_menu():
    print("""
=== RC Calibration ===
  w = rear motor forward burst ({}s @ {}% duty)
  s = motor stop
  c = servo center  ({}°)
  a = servo left     ({}°)
  d = servo right    ({}°)
  l = live sensor monitor (Ctrl-C to exit monitor)
  q = quit
""".format(motor.BURST_TIME, motor.PWM_DUTY,
           motor.ANGLE_CENTER, motor.ANGLE_LEFT, motor.ANGLE_RIGHT))


def live_sensor_monitor():
    print("[SENSOR] Live monitor - wave the black line under each sensor. Ctrl-C to stop.")
    try:
        while True:
            left, right = sensor.read()
            print(f"Left: {'BLACK' if left else 'WHITE'} | Right: {'BLACK' if right else 'WHITE'}")
            sleep(0.2)
    except KeyboardInterrupt:
        print("\n[SENSOR] Monitor stopped.")


def main():
    sensor.setup()
    motor.setup_servo()
    print("[INFO] Servo centered, sensors + motor ready.")

    try:
        while True:
            print_menu()
            key = read_key().lower()

            if key == 'w':
                print("[MOTOR] Forward burst...")
                motor.forward()
                print("[MOTOR] Done.")
            elif key == 's':
                motor.stop()
                print("[MOTOR] Stopped, servo re-centered.")
            elif key == 'c':
                motor.set_servo_angle(motor.ANGLE_CENTER)
                print(f"[SERVO] Center ({motor.ANGLE_CENTER}°)")
            elif key == 'a':
                motor.set_servo_angle(motor.ANGLE_LEFT)
                print(f"[SERVO] Left ({motor.ANGLE_LEFT}°)")
            elif key == 'd':
                motor.set_servo_angle(motor.ANGLE_RIGHT)
                print(f"[SERVO] Right ({motor.ANGLE_RIGHT}°)")
            elif key == 'l':
                live_sensor_monitor()
            elif key == 'q':
                break
    finally:
        motor.stop()
        sensor.cleanup()
        print("\n[INFO] Cleaned up GPIO - goodbye!")


if __name__ == "__main__":
    main()
