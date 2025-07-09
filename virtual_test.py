import cv2
import numpy as np

# Constants
CM_PER_PIXEL = 0.01233  # Adjust based on calibration
MIN_LINE_WIDTH = 100     # Minimum valid line width in pixels
MAX_DEVIATION_CM = 0.6   # Acceptable deviation in cm to be considered "on track"
DOMINANCE_RATIO = 1.5
MIN_TOTAL_BLACK_PX = 1000

# --- Settings ---
VIDEO_PATH = r"C:\Users\harry\LITS internship 2025\Line following program\route1.mp4"  # Replace with your actual path
calibration_x = None  # Will be set from the first valid frame

# --- Thresholding Function ---
def threshold_image(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([179, 255, 50])  # Tune this if needed
    mask = cv2.inRange(hsv, lower_black, upper_black)
    kernel = np.ones((3, 3), np.uint8)
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    return cleaned

# --- Line Center Detection ---
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
def fallback_direction(thresh_img, frame_width):
    total_black = cv2.countNonZero(thresh_img)
    if total_black < MIN_TOTAL_BLACK_PX:
        return "NO LINE DETECTED"

    left = thresh_img[:, :frame_width // 2]
    right = thresh_img[:, frame_width // 2:]
    left_count = cv2.countNonZero(left)
    right_count = cv2.countNonZero(right)

    if left_count > right_count * DOMINANCE_RATIO:
        return "TURN LEFT (Fallback)"
    elif right_count > left_count * DOMINANCE_RATIO:
        return "TURN RIGHT (Fallback)"
    else:
        return "UNCERTAIN"

# --- Main Video Analysis ---
cap = cv2.VideoCapture(VIDEO_PATH)
frame_number = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame_number += 1
    resized = cv2.resize(frame, (480, 240))
    height, width = resized.shape[:2]
    thresh = threshold_image(resized)
    center_x, line_width = detect_line_center(thresh)

    decision = ""

    if center_x is not None and line_width > MIN_LINE_WIDTH:
        if calibration_x is None:
            calibration_x = center_x
            print(f"[Calibration] Set center X to {calibration_x} (frame {frame_number})")

        deviation = center_x - calibration_x
        deviation_cm = round(deviation * CM_PER_PIXEL, 2)

        if abs(deviation_cm) < MAX_DEVIATION_CM:
            decision = "ON TRACK → Move Forward"
        elif deviation_cm < 0:
            decision = f"Deviation {deviation_cm}cm → TURN LEFT"
        else:
            decision = f"Deviation {deviation_cm}cm → TURN RIGHT"
    else:
        decision = fallback_direction(thresh, width)

    # Draw overlays
    center_line = width // 2
    cv2.line(resized, (center_line, 0), (center_line, height), (255, 0, 0), 2)
    if center_x is not None:
        cv2.circle(resized, (center_x, height // 2), 5, (0, 255, 0), -1)
    cv2.putText(resized, f"Decision: {decision}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    cv2.imshow("Line Following Debug", resized)
    cv2.imshow("Threshold", thresh)

    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
