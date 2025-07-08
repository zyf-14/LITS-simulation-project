import cv2
import numpy as np

# === CONFIG ===
IMAGE_PATH = r"C:\Users\harry\LITS internship 2025\pic1.jpg"  # <-- Update path if needed
REFERENCE_Y = 359  # Calibrated vertical position of black line

# === LOAD IMAGE ===
image = cv2.imread(IMAGE_PATH)
if image is None:
    print("❌ Error: Could not load image.")
    exit()

# Resize for consistency
image = cv2.resize(image, (480, 240))
height, width = image.shape[:2]
center_x = width // 2

# === THRESHOLDING ===
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)

# === EXTRACT HORIZONTAL BAND AROUND REFERENCE_Y ===
band_height = 4  # Use ±2 pixels
band = thresh[REFERENCE_Y - 2:REFERENCE_Y + 2, :]

# === SUM BLACK PIXELS IN EACH COLUMN ===
black_intensity = np.sum(band == 255, axis=0)  # 255 means black (in inverted threshold)
line_x = np.argmax(black_intensity)

# === CALCULATE DEVIATION FROM CENTER ===
deviation = line_x - center_x

# === OUTPUT ===
print(f"📏 Fixed Center X: {center_x}")
print(f"🎯 Detected Line X: {line_x}")
print(f"➡️ Deviation from center: {deviation} px")

# === DRAW VISUAL LINES ===
output = image.copy()
cv2.line(output, (center_x, 0), (center_x, height), (0, 255, 255), 2)  # Fixed center line (yellow)
cv2.line(output, (line_x, 0), (line_x, height), (0, 0, 255), 2)        # Detected line (red)

cv2.putText(output, f"Deviation: {deviation}px", (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

cv2.imshow("Deviation Detection", output)
cv2.waitKey(0)
cv2.destroyAllWindows()
