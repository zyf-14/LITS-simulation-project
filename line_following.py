# === line_following.py ===
import cv2
import numpy as np
import config

def process_frame(thresh_img, frame=None, calibration_x=None, last_known_side=None):
    height, width = thresh_img.shape
    center_x, line_width = config.detect_line_center(thresh_img)

    debug = {
        "center_x": center_x,
        "line_width": line_width,
        "calibration_x": calibration_x,
        "deviation_cm": None,
        "fallback": False,
        "direction": None
    }

    # Valid line detected
    if center_x is not None and line_width > config.MIN_LINE_WIDTH_PX:
        if calibration_x is None:
            calibration_x = center_x  # First valid center becomes reference

        deviation = center_x - calibration_x
        deviation_cm = round(deviation * config.CM_PER_PIXEL, 2)
        debug["deviation_cm"] = deviation_cm

        if abs(deviation_cm) < config.MAX_DEVIATION_CM:
            debug["direction"] = "FORWARD"
        elif deviation_cm < 0:
            debug["direction"] = "LEFT"
        else:
            debug["direction"] = "RIGHT"

        return debug["direction"], debug, calibration_x

    # Fallback logic: estimate from left/right black pixel dominance
    fallback = config.fallback_direction(thresh_img, width)
    debug["fallback"] = True
    debug["direction"] = fallback
    return fallback, debug, calibration_x
