# === raw_sensor_check.py ===
# Diagnostic for sensor.py mismatches: shows the RAW GPIO level on each
# sensor pin (no BLACK/WHITE interpretation, no inversion logic) so it can
# be compared directly against the sensor module's own onboard LED.
#
# Usage:
#   python3 raw_sensor_check.py            # floating input (matches sensor.py's current setup)
#   python3 raw_sensor_check.py pud_up     # same pins, with internal pull-up enabled
#   python3 raw_sensor_check.py pud_down   # same pins, with internal pull-down enabled
#
# Run all three if the first one looks wrong/noisy - if pud_up and pud_down
# both stabilize it (into an inverted-but-consistent reading), it means the
# sensor's output is open-collector and needs a real pull resistor, not a
# code fix. If floating already looks stable but just inverted relative to
# the LED, it's a logic-inversion fix in sensor.py, not a wiring problem.

import sys
from time import sleep, strftime
import RPi.GPIO as GPIO

LEFT_SENSOR_PIN  = 25  # BCM - physical pin 22
RIGHT_SENSOR_PIN = 22  # BCM - physical pin 15

mode = sys.argv[1] if len(sys.argv) > 1 else "float"
pud_map = {
    "float":   GPIO.PUD_OFF,
    "pud_up":  GPIO.PUD_UP,
    "pud_down": GPIO.PUD_DOWN,
}
if mode not in pud_map:
    print(f"Unknown mode '{mode}'. Use: float | pud_up | pud_down")
    sys.exit(1)

GPIO.setmode(GPIO.BCM)
GPIO.setup(LEFT_SENSOR_PIN, GPIO.IN, pull_up_down=pud_map[mode])
GPIO.setup(RIGHT_SENSOR_PIN, GPIO.IN, pull_up_down=pud_map[mode])

print(f"[MODE] {mode}  (LEFT=GPIO{LEFT_SENSOR_PIN}/pin22, RIGHT=GPIO{RIGHT_SENSOR_PIN}/pin15)")
print("[INFO] Raw HIGH/LOW only - no BLACK/WHITE interpretation. Ctrl-C to stop.")
print("[INFO] Watch this against the sensor module's own onboard LED as you move it over the line.\n")

last_left, last_right = None, None
try:
    while True:
        left = GPIO.input(LEFT_SENSOR_PIN)
        right = GPIO.input(RIGHT_SENSOR_PIN)
        changed = (left != last_left) or (right != last_right)
        marker = "  <-- changed" if changed else ""
        print(f"[{strftime('%H:%M:%S')}] LEFT(GPIO{LEFT_SENSOR_PIN})={'HIGH' if left else 'LOW '}   RIGHT(GPIO{RIGHT_SENSOR_PIN})={'HIGH' if right else 'LOW '}{marker}")
        last_left, last_right = left, right
        sleep(0.2)
except KeyboardInterrupt:
    print("\n[INFO] Stopped.")
finally:
    GPIO.cleanup()
