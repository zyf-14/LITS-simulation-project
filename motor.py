# === motor.py ===
import RPi.GPIO as GPIO
from time import sleep, time

# Define GPIO pins
FIN1, FIN2 = 23, 24  # Front motor
BIN1, BIN2 = 27, 17  # Back motor

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for pin in [FIN1, FIN2, BIN1, BIN2]:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

last_turn = None

def software_pwm(pin1, pin2, duty_cycle, duration=0.3, freq=100):
    period = 1.0 / freq
    on_time = period * (duty_cycle / 100.0)
    off_time = period - on_time
    start_time = time()
    while (time() - start_time) < duration:
        GPIO.output(pin1, GPIO.HIGH)
        GPIO.output(pin2, GPIO.LOW)
        sleep(on_time)
        GPIO.output(pin1, GPIO.LOW)
        GPIO.output(pin2, GPIO.LOW)
        sleep(off_time)

def forward():
    software_pwm(BIN1, BIN2, duty_cycle=18, duration=0.2)

def left():
    global last_turn
    software_pwm(FIN2, FIN1, duty_cycle=20, duration=0.15)
    last_turn = 'l'

def right():
    global last_turn
    software_pwm(FIN1, FIN2, duty_cycle=20, duration=0.15)
    last_turn = 'r'

def realign_steering(duration=0.2, duty=30):
    global last_turn
    if last_turn == 'l':
        print("Auto realigning from LEFT")
        software_pwm(FIN1, FIN2, duty, duration)
    elif last_turn == 'r':
        print("Auto realigning from RIGHT")
        software_pwm(FIN2, FIN1, duty, duration)
    last_turn = None

def stop():
    for pin in [FIN1, FIN2, BIN1, BIN2]:
        GPIO.output(pin, GPIO.LOW)
