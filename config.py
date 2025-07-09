# === config.py ===
import numpy as np
import cv2

# --- Physical Calibration ---
CM_PER_PIXEL = 0.01233  # Based on your 3.5cm height from ground
MAIN_LINE_WIDTH_CM = 1.8
MAIN_LINE_WIDTH_PX = int(MAIN_LINE_WIDTH_CM / CM_PER_PIXEL)
MAX_DEVIATION_CM = 0.6
MIN_LINE_WIDTH_PX = 100
DOMINANCE_RATIO = 1.5
MIN_TOTAL_BLACK_PX = 1000

# --- Thresholding ---
def threshold_image(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([179, 255, 50])
    mask = cv2.inRange(hsv, lower_black, upper_black)
    kernel = np.ones((3, 3), np.uint8)
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    return cleaned

# --- Line Detection ---
def detect_line_center(thresh_img):
    contours, _ = cv2.findContours(thresh_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, 0

    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)
    if w < 30 or h < 10:
        return None, 0

    cx = x + w // 2
    return cx, w

# --- Fallback Direction Logic ---
def fallback_direction(thresh_img, width):
    total_black = cv2.countNonZero(thresh_img)
    if total_black < MIN_TOTAL_BLACK_PX:
        return "NO LINE DETECTED"

    left = thresh_img[:, :width // 2]
    right = thresh_img[:, width // 2:]
    left_count = cv2.countNonZero(left)
    right_count = cv2.countNonZero(right)

    if left_count > right_count * DOMINANCE_RATIO:
        return "TURN LEFT (Fallback)"
    elif right_count > left_count * DOMINANCE_RATIO:
        return "TURN RIGHT (Fallback)"
    else:
        return "UNCERTAIN"
