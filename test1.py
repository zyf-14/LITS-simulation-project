import RPi.GPIO as GPIO
from time import sleep

# GPIO Pins
LEFT_SENSOR_PIN = 22
RIGHT_SENSOR_PIN = 5
SERVO_PIN = 18

# Setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(LEFT_SENSOR_PIN, GPIO.IN)
GPIO.setup(RIGHT_SENSOR_PIN, GPIO.IN)
GPIO.setup(SERVO_PIN, GPIO.OUT)

pwm = GPIO.PWM(SERVO_PIN, 50)  # 50Hz for SG90 servo
pwm.start(0)

# New Angle Settings
ANGLE_LEFT = 70
ANGLE_RIGHT = 90
ANGLE_ORIGIN = 80

def angle_to_duty(angle):
    return 2 + (angle / 18)

def move_servo_to(angle):
    duty = angle_to_duty(angle)
    pwm.ChangeDutyCycle(duty)
    sleep(0.3)
    pwm.ChangeDutyCycle(0)

def read_sensor(pin):
    return "Black" if GPIO.input(pin) == 1 else "White"

try:
    print("=== Servo + Sensor Test (1 input at a time) ===")
    while True:
        # Read sensor values
        left_color = read_sensor(LEFT_SENSOR_PIN)
        right_color = read_sensor(RIGHT_SENSOR_PIN)

        # Print reading
        print(f"[IR SENSOR] Left: {left_color} | Right: {right_color}")
        sleep(0.7)

        # Get user input
        direction = input("Enter direction (l, r, o): ").lower().strip()
        if direction == "l":
            print(f"👉 Turning Left ({ANGLE_LEFT}°)")
            move_servo_to(ANGLE_LEFT)
        elif direction == "r":
            print(f"👉 Turning Right ({ANGLE_RIGHT}°)")
            move_servo_to(ANGLE_RIGHT)
        elif direction == "o":
            print(f"👉 Returning to Origin ({ANGLE_ORIGIN}°)")
            move_servo_to(ANGLE_ORIGIN)
        else:
            print("❌ Invalid input. Use only: l, r, or o.")

except KeyboardInterrupt:
    print("\nTest interrupted by user.")

finally:
    pwm.stop()
    GPIO.cleanup()
    print("GPIO cleanup complete. Test ended.")
