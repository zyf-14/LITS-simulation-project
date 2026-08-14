#ifndef MAIN_H
#define MAIN_H

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include <ESPmDNS.h>
#include "config.h"

// ===== WiFi =====
// WIFI_SSID / WIFI_PASSWORD live in config.h (gitignored) - copy config.example.h
// to config.h and fill in real values.
constexpr unsigned long WIFI_CONNECT_TIMEOUT_MS = 15000;
constexpr unsigned long WIFI_WATCHDOG_INTERVAL_MS = 5000;

// Static IP so the ESP32 stops moving around on every DHCP lease/reboot - both the
// terminal Pi's PHP and the RC Pi's Python have historically had to be re-pointed
// whenever this changed. .250 picked as an address near the top of the /20 range,
// away from where DHCP pools typically start handing out leases; confirmed free via
// ping before picking it. Network is 192.168.0.0/20 (255.255.240.0), gateway/DNS
// 192.168.0.1 - matches the RC Pi's own routing on the LiTS2_5G network.
constexpr bool USE_STATIC_IP = true;
IPAddress STATIC_IP(192, 168, 15, 250);
IPAddress STATIC_GATEWAY(192, 168, 0, 1);
IPAddress STATIC_SUBNET(255, 255, 240, 0);
IPAddress STATIC_DNS(192, 168, 0, 1);

// The ESP32, servo, and both ultrasonic sensors share one power rail with no headroom
// to split it. Trimming radio power draw here reduces the peak current the WiFi radio
// pulls right as a /open_gate request comes in and is answered - which happens at
// essentially the same instant the servo starts moving and drawing its own current.
// If range/reliability suffers, step this up (WIFI_POWER_11dBm, _13dBm, ...); if
// brownouts persist, step it down further (WIFI_POWER_5dBm, _2dBm).
constexpr wifi_power_t WIFI_TX_POWER = WIFI_POWER_8_5dBm;
// Modem sleep (radio dozes between beacons to save average current) made the first
// request after any idle period slow/unreliable - the radio has to wake up first,
// which could exceed a caller's timeout (e.g. the terminal Pi's 2s curl timeout).
// Disabled: consistent responsiveness matters more here than the extra average draw,
// and WIFI_TX_POWER above already covers the peak-current side of the brownout risk.
constexpr bool WIFI_ENABLE_MODEM_SLEEP = false;

// ===== mDNS =====
// Reachable as boomgate.local regardless of which network/IP this ends up on -
// avoids hardcoding an IP that breaks when it changes networks or renews its DHCP lease.
constexpr char MDNS_HOSTNAME[] = "boomgate";

// ===== Terminal Pi notification =====
// Entry sensor -> begin the (simulated) LPR cycle: demo_trigger.php sets detect_car=1
// and drops the known-authorized test plate into /dev/shm/validated/, standing in for
// the real camera+OCR step - see /opt/dev/create_validate.sh on the terminal Pi for
// the original dev fixture this replaces. MAR5052 is confirmed registered/authorized
// on the real backend.
constexpr bool ENABLE_TERMINAL_PI_NOTIFY = true;
constexpr char TERMINAL_PI_NOTIFY_URL[] = "http://192.168.1.15/demo_trigger.php?plate=MAR5052";
constexpr unsigned long TERMINAL_PI_NOTIFY_TIMEOUT_MS = 3000;

// Exit sensor cleared -> tell the terminal Pi the car has left, resetting detect_car
// back to 0 so the next cycle starts clean. Reuses the vendor's own existing endpoint.
constexpr char TERMINAL_PI_RESET_URL[] = "http://192.168.1.15/detect_car.php?detect_car=0";

// ===== Cores =====
constexpr int CPU_0 = 0;
constexpr int CPU_1 = 1;

// ===== Indicator =====
constexpr int LED_INDICATOR = 2;

// ===== Boom servo =====
constexpr int SERVO_PIN    = 13;
constexpr int OPEN_ANGLE   = 110;
// A couple degrees off the hard mechanical stop, rather than exactly 0 - sitting right
// at the stop can leave the servo pushing/holding against it continuously (extra current
// draw), which doesn't help the shared-rail power situation.
constexpr int CLOSED_ANGLE = 4;
constexpr unsigned long GATE_TRIGGER_COOLDOWN_MS = 100;

enum GateCommand : uint8_t {
    GATE_IDLE  = 0,
    GATE_OPEN  = 1,
    GATE_CLOSE = 2,
};

// ===== Ultrasonic sensors =====
// Entry sensor: detects a vehicle arriving, used to notify the terminal Pi to start LPR.
constexpr int TRIG_ENTRY = 15;
constexpr int ECHO_ENTRY = 5;
// Exit sensor: detects the vehicle clearing the gate, used to auto-close.
// NOTE: previously TRIG_2 was GPIO2, which collides with LED_INDICATOR. Moved to GPIO4.
constexpr int TRIG_EXIT = 4;
constexpr int ECHO_EXIT = 18;

constexpr int DISTANCE_THRESHOLD_CM  = 8;
constexpr unsigned long SENSOR_ECHO_TIMEOUT_US = 30000UL; // pulseIn timeout
constexpr unsigned long SENSOR_POLL_INTERVAL_MS = 50;
// The exit sensor can flicker present/absent rapidly when something sits near the
// threshold distance (observed directly during testing). Require it to read clear
// continuously for this long before treating it as the vehicle genuinely passing
// through, rather than closing on a single noisy sample.
constexpr unsigned long EXIT_CLEAR_CONFIRM_MS = 800;
// Same threshold-flicker behavior as the exit sensor above, but on the entry side's
// "vehicle just arrived" edge - which had NO debounce at all until this was added.
// That's worse than it sounds here: unlike a spurious exit reading (caught by the
// presence interlock before it can do anything unsafe), a single noisy entry blip
// fires a real notifyTerminalPiVehicleDetected() call with a plate the backend
// already has pre-authorized (see TERMINAL_PI_NOTIFY_URL below) - so it doesn't
// get discarded as a false alarm, it completes a real authorized gate-open.
// Observed causing the gate to open with nothing there. Shorter than the exit
// window since there's no safety case for stretching it further, just noise
// filtering.
constexpr unsigned long ENTRY_PRESENT_CONFIRM_MS = 300;
// A pulseIn timeout (no echo) was being treated identically to "vehicle actually
// left" on the entry side - same dropout-vs-clear conflation the exit sensor had
// before its 2026-08-12 fix, just never applied here. Observed live: with a vehicle
// sitting stationary at a steady 4cm reading, occasional -1cm dropouts (roughly
// every 1-3s) instantly cleared vehicle_at_entry, which (a) opened a brief window
// where the presence interlock didn't protect against a real close if the exit
// sensor's own clear-confirm fired at the same moment, and (b) re-armed the
// arrival debounce, causing a spurious re-notify/re-open once the sensor recovered.
// This is what caused the gate to close and reopen on its own with a stationary
// vehicle. Only a genuine in-range-or-beyond echo now counts as clearing; a
// dropout just holds state, same as the exit sensor already does.
// Update 2026-08-14: 500ms still wasn't enough - observed live re-triggering
// the whole entry->OCR cycle from scratch 4 times in ~90s because the entry
// sensor kept reading clear (marginal vehicle positioning at the sensor's
// edge) just long enough to flip vehicle_at_entry false, which then let the
// exit sensor's independent reset call slip through the entry-presence guard
// each time. Raised substantially so a brief/marginal clear reading can't
// tip this over as easily.
constexpr unsigned long ENTRY_CLEAR_CONFIRM_MS = 2000;
// A pulseIn timeout (no echo) looks identical to "vehicle far away" - both make
// readDistanceCm() return -1. If the exit sensor drops out (bad reflection angle,
// loose wire) while a vehicle is still sitting under the gate, that must NOT be
// trusted as "clear", or the gate would auto-close on top of the vehicle. Only a
// valid in-range echo counts towards the clear-confirm debounce above; throttle how
// often a dropout gets logged so a dead sensor doesn't spam Serial every 50ms poll.
constexpr unsigned long EXIT_SENSOR_FAULT_LOG_INTERVAL_MS = 2000;
// The exit sensor's "vehicle just arrived" edge had NO debounce at all - unlike
// entry, which got ENTRY_PRESENT_CONFIRM_MS above. A single noisy reading near the
// threshold (the same flicker EXIT_CLEAR_CONFIRM_MS was built for) was enough to
// instantly set vehicle_at_exit=true, and once the flicker cleared again it would
// complete a full present->confirmed-clear cycle on its own - which fires
// notifyTerminalPiVehicleLeft() (see TERMINAL_PI_RESET_URL below), resetting the
// terminal Pi's detect_car flag with no real vehicle involved. That silently killed
// the LPR5Lite capture window every time it happened, discovered while investigating
// why the on-device OCR never got a chance to run despite the entry trigger firing.
// Same debounce length as entry's, same rationale - noise filtering only.
constexpr unsigned long EXIT_PRESENT_CONFIRM_MS = 300;
// Demo/test-mode only: also close the gate once the vehicle clears the ENTRY sensor,
// not just the exit sensor. Requested to test the front-sensor-only flow (entry
// sensor only - exit sensor deliberately not used in this test) end-to-end without
// needing a full drive-through past the exit sensor. Goes through the same
// taskBoomgate presence interlock as the exit-triggered close, so it still won't
// actually move the servo if either sensor shows presence at the moment it's due to
// fire - but the trigger condition itself (entry clearing) is weaker evidence of a
// safe close than the exit sensor confirming genuine pass-through. NOT appropriate
// for a real deployment: entry's field of view is narrow, so a vehicle can clear it
// while still physically under the barrier. Set to false to revert to the original
// exit-sensor-only close behavior.
constexpr bool CLOSE_ON_ENTRY_CLEAR = false;

// ===== Shared state (written from one task, read from others -> must be volatile) =====
extern Servo boomServo;
extern WebServer httpServer;
extern volatile uint8_t boomgate_status;
extern volatile bool    gate_is_open;
extern volatile bool    vehicle_at_entry;
extern volatile bool    vehicle_at_exit;
extern volatile uint32_t total_uptime;

// ===== Setup helpers =====
void connectWiFi();
void setupMdns();
void setupHttpServer();
void initThreads();

// ===== HTTP handlers =====
void handleOpenGate();
void handleCloseGate();
void handleStatus();
void handleSetAngle();

// ===== Sensing =====
long readDistanceCm(int trigPin, int echoPin);
void notifyTerminalPiVehicleDetected();
void notifyTerminalPiVehicleLeft();
void notifyTerminalPiResetFromEntryClear();

// ===== Tasks =====
void taskHeartBeat(void *pvParameters);
void taskBoomgate(void *pvParameters);
void taskSensors(void *pvParameters);
void taskWifiWatchdog(void *pvParameters);

#endif
