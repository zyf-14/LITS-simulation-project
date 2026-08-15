# === sensor.py ===
import RPi.GPIO as GPIO
import threading
import time

LEFT_SENSOR_PIN  = 22
RIGHT_SENSOR_PIN = 25

class SensorReader(threading.Thread):
    def __init__(self, poll_delay=0.01):
        super().__init__()
        self.left = 0
        self.right = 0
        self.poll_delay = poll_delay
        self.running = False
        self.lock = threading.Lock()

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(LEFT_SENSOR_PIN, GPIO.IN)
        GPIO.setup(RIGHT_SENSOR_PIN, GPIO.IN)

    def read_sensors(self):
        # IR sensors return: LOW on WHITE, HIGH on BLACK → so invert
        raw_left  = GPIO.input(LEFT_SENSOR_PIN)
        raw_right = GPIO.input(RIGHT_SENSOR_PIN)
        return int(raw_left), int(raw_right)

    def get(self):
        with self.lock:
            return self.left, self.right

    def run(self):
        self.running = True
        while self.running:
            left, right = self.read_sensors()
            with self.lock:
                self.left = left
                self.right = right
            time.sleep(self.poll_delay)

    def shutdown(self):
        self.running = False
        self.join()
        GPIO.cleanup()

# === Example usage ===
if __name__ == "__main__":
    sensor = SensorReader()
    sensor.start()

    try:
        while True:
            l, r = sensor.get()
            print(f"Left: {l}, Right: {r}")
            time.sleep(0.001)
    except KeyboardInterrupt:
        sensor.shutdown()

