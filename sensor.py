# === sensor.py ===
import RPi.GPIO as GPIO

LEFT_SENSOR_PIN  = 22   # BCM
RIGHT_SENSOR_PIN = 25   # BCM

def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LEFT_SENSOR_PIN, GPIO.IN)
    GPIO.setup(RIGHT_SENSOR_PIN, GPIO.IN)

def read():
    # Sensor returns LOW on WHITE, HIGH on BLACK — so we invert logic
    return GPIO.input(LEFT_SENSOR_PIN), GPIO.input(RIGHT_SENSOR_PIN)

def cleanup():
    GPIO.cleanup()
