# === picam_trigger.py ===
import cv2
from picamera2 import Picamera2
import time

TRIGGER_THRESHOLD = 1000  # Pixel count threshold to detect black

picam = Picamera2()
picam.configure(picam.create_preview_configuration(main={"format": 'XRGB8888', "size": (320, 240)}))
picam.start()
time.sleep(1)

def wait_for_black_trigger():
    while True:
        frame = picam.capture_array()
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)

        black_pixels = cv2.countNonZero(thresh)
        print(f"[PiCam] Black pixel count: {black_pixels}")

        if black_pixels > TRIGGER_THRESHOLD:
            print("[PiCam] Trigger line detected!")
            return

        time.sleep(0.1)
