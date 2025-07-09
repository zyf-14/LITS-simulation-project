# === main.py ===
import cv2
from picamera2 import Picamera2
from time import sleep, time

import config
import motor
import line_following  # 👈 NEW

# Camera setup
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"size": (640, 480)}))
picam2.start()
sleep(2)

log_file = open("debug_log.txt", "w")
last_known_side = None
last_line_seen_time = time()
line_missing = False
calibration_x = None

def log(message):
    timestamp = time()
    print(message)
    log_file.write(f"[{timestamp:.2f}] {message}\n")
    log_file.flush()

try:
    while True:
        frame = picam2.capture_array()
        frame = cv2.flip(cv2.rotate(frame, cv2.ROTATE_180), 1)
        resized = cv2.resize(frame, (480, 240))
        height, width = resized.shape[:2]

        thresh = config.threshold_image(resized)

        # === Call the line following module ===
        direction, debug, calibration_x = line_following.process_frame(
            thresh_img=thresh,
            frame=resized,
            calibration_x=calibration_x,
            last_known_side=last_known_side
        )

        center_x = debug["center_x"]
        if center_x is not None:
            cv2.circle(resized, (center_x, height // 2), 5, (0, 255, 0), -1)
        if calibration_x is not None:
            cv2.line(resized, (calibration_x, 0), (calibration_x, height), (255, 0, 0), 2)

        if direction == "FORWARD":
            log(f"✅ ON TRACK → Forward (Offset: {debug['deviation_cm']} cm)")
            motor.forward()
            motor.realign_steering()
            last_line_seen_time = time()
            line_missing = False
        elif direction == "LEFT":
            log(f"⬅️ Turn LEFT (Offset: {debug['deviation_cm']} cm)")
            motor.left()
            last_known_side = 'left'
            last_line_seen_time = time()
            line_missing = False
        elif direction == "RIGHT":
            log(f"➡️ Turn RIGHT (Offset: {debug['deviation_cm']} cm)")
            motor.right()
            last_known_side = 'right'
            last_line_seen_time = time()
            line_missing = False
        elif direction == "RECOVERY" or debug["fallback"]:
            log("❌ Line lost → recovery mode")
            if time() - last_line_seen_time > 3:
                log("🛑 Line not found for 3s → Stopping")
                motor.stop()
                break
            motor.forward()
            if last_known_side == 'left':
                motor.left()
            elif last_known_side == 'right':
                motor.right()
            else:
                motor.left()

        cv2.imshow("Threshold", thresh)
        cv2.imshow("Debug", resized)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    log("Stopped by user.")

finally:
    motor.stop()
    log_file.close()
    picam2.stop()
    cv2.destroyAllWindows()
