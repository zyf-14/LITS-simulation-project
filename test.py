import cv2
import numpy as np

# === CONFIG ===
IMAGE_PATH = r"C:\Users\harry\LITS internship 2025\pic1.jpg"
REFERENCE_Y = 359
CM_PER_PIXEL = 0.01233
EXPECTED_LINE_WIDTH_CM = 1.8
EXPECTED_WIDTH_PX = int(EXPECTED_LINE_WIDTH_CM / CM_PER_PIXEL)  # ≈ 146px

last_known_deviation = 0

# === LOAD IMAGE ===
image = cv2.imread(IMAGE_PATH)
if image is None:
    print("❌ Error: Could not load image.")
    exit()

image = cv2.resize(image, (480, 240))
height, width = image.shape[:2]
center_x = width // 2

# === THRESHOLDING ===
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)

# === HORIZONTAL BAND ===
band = thresh[REFERENCE_Y - 2:REFERENCE_Y + 2, :]
black_intensity = np.sum(band == 255, axis=0)
line_x = np.argmax(black_intensity)
line_width = np.count_nonzero(black_intensity > 0)

# === DEVIATION ===
deviation = line_x - center_x

# === RECOVERY + DIRECTION LOGIC ===
status = ""
if line_width < EXPECTED_WIDTH_PX * 0.6:
    # Incomplete line, analyze pixel distribution
    left_half = black_intensity[:center_x]
    right_half = black_intensity[center_x:]

    left_sum = np.sum(left_half)
    right_sum = np.sum(right_half)

    print(f"🔍 Black pixel distribution → Left: {left_sum}, Right: {right_sum}")

    if left_sum > right_sum * 1.2:  # 20% more concentrated on left
        status = "🛑 Partial line on LEFT → Turn LEFT to recover"
        last_known_deviation = -1
    elif right_sum > left_sum * 1.2:
        status = "🛑 Partial line on RIGHT → Turn RIGHT to recover"
        last_known_deviation = 1
    else:
        # Fallback: use last known direction
        if last_known_deviation < 0:
            status = "🛑 Unknown partial line → Turn LEFT (fallback)"
        else:
            status = "🛑 Unknown partial line → Turn RIGHT (fallback)"
else:
    # Normal detection
    if abs(deviation) < 10:
        status = "✅ Line centered → Move STRAIGHT"
    elif deviation < 0:
        status = "↩️ Line left → Adjust LEFT"
        last_known_deviation = -1
    else:
        status = "↪️ Line right → Adjust RIGHT"
        last_known_deviation = 1

# === VISUALIZE ===
output = image.copy()
cv2.line(output, (center_x, 0), (center_x, height), (0, 255, 255), 2)  # Fixed center
cv2.line(output, (line_x, 0), (line_x, height), (0, 0, 255), 2)        # Detected line

cv2.putText(output, status, (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

cv2.imshow("Line Tracking + Smart Recovery", output)
cv2.waitKey(0)
cv2.destroyAllWindows()

# === LOG OUTPUT ===
print(f"📏 Center X: {center_x}")
print(f"🎯 Line X: {line_x} (Width: {line_width}px, Expected: {EXPECTED_WIDTH_PX}px)")
print(f"➡️ Deviation: {deviation}px → {status}")
