#include <Arduino.h>
#include <HTTPClient.h>
#include "main.h"

Servo boomServo;
WebServer httpServer(80);

volatile uint8_t  boomgate_status = GATE_IDLE;
volatile bool     gate_is_open = false;
volatile bool     vehicle_at_entry = false;
volatile bool     vehicle_at_exit  = false;
volatile uint32_t total_uptime = 0;
// Set when exit-clear wants to notify the terminal Pi "vehicle left" but
// vehicle_at_entry is true at that moment (so the notify is suppressed to
// avoid resetting an in-progress LPR cycle) - consumed on entry's next
// clear-confirm edge instead of being dropped. See taskSensors.
volatile bool     pendingVehicleLeftNotify = false;

void setup() {
    Serial.begin(115200);
    delay(200);

    connectWiFi();
    setupMdns();
    setupHttpServer();
    initThreads();
}

void loop() {
    httpServer.handleClient();
}

void connectWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.persistent(true);
    WiFi.setTxPower(WIFI_TX_POWER);
    WiFi.setSleep(WIFI_ENABLE_MODEM_SLEEP);

    if (USE_STATIC_IP) {
        if (!WiFi.config(STATIC_IP, STATIC_GATEWAY, STATIC_SUBNET, STATIC_DNS)) {
            Serial.println("[WIFI] Static IP config failed - falling back to DHCP");
        }
    }

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    Serial.printf("[WIFI] Connecting to %s", WIFI_SSID);
    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - start) < WIFI_CONNECT_TIMEOUT_MS) {
        delay(300);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.print("[WIFI] Connected, IP = ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("[WIFI] Not connected yet - watchdog task will keep retrying");
    }
}

void setupMdns() {
    MDNS.end(); // safe no-op if not already started; ensures a clean (re)start
    if (MDNS.begin(MDNS_HOSTNAME)) {
        MDNS.addService("http", "tcp", 80);
        Serial.printf("[MDNS] Registered as %s.local\n", MDNS_HOSTNAME);
    } else {
        Serial.println("[MDNS] Failed to start");
    }
}

void setupHttpServer() {
    httpServer.on("/open_gate", HTTP_GET, handleOpenGate);
    httpServer.on("/close_gate", HTTP_GET, handleCloseGate);
    httpServer.on("/status", HTTP_GET, handleStatus);
    httpServer.on("/set_angle", HTTP_GET, handleSetAngle);
    httpServer.begin();
    Serial.println("[HTTP] Server listening on port 80");
}

void handleOpenGate() {
    boomgate_status = GATE_OPEN;
    Serial.println("[HTTP] /open_gate -> opening");
    httpServer.send(200, "text/plain", "OK: opening gate");
}

void handleCloseGate() {
    boomgate_status = GATE_CLOSE;
    Serial.println("[HTTP] /close_gate -> closing");
    httpServer.send(200, "text/plain", "OK: closing gate");
}

// Temporary calibration helper - writes the servo directly to an arbitrary angle,
// bypassing boomgate_status/gate_is_open entirely (this does NOT update gate state,
// it's purely for finding the right CLOSED_ANGLE/OPEN_ANGLE values after the barrier
// arm was reattached to the servo horn at a different spline position than before,
// which flipped which physical direction "open" swings relative to the old angles).
// GET /set_angle?a=NN, NN in [0,180]. Remove once CLOSED_ANGLE/OPEN_ANGLE are re-tuned.
void handleSetAngle() {
    if (!httpServer.hasArg("a")) {
        httpServer.send(400, "text/plain", "Missing ?a=<0-180>");
        return;
    }
    int angle = httpServer.arg("a").toInt();
    if (angle < 0 || angle > 180) {
        httpServer.send(400, "text/plain", "Angle out of range [0,180]");
        return;
    }
    boomServo.write(angle);
    char buf[48];
    snprintf(buf, sizeof(buf), "OK: servo set to %d", angle);
    Serial.printf("[CALIBRATE] /set_angle -> %d\n", angle);
    httpServer.send(200, "text/plain", buf);
}

void handleStatus() {
    char buf[330];
    snprintf(buf, sizeof(buf),
        "{\"gate_status\":%u,\"gate_is_open\":%s,\"vehicle_at_entry\":%s,\"vehicle_at_exit\":%s,"
        "\"uptime_s\":%u,\"wifi_connected\":%s,\"rssi\":%d,\"ip\":\"%s\",\"hostname\":\"%s.local\"}",
        boomgate_status,
        gate_is_open ? "true" : "false",
        vehicle_at_entry ? "true" : "false",
        vehicle_at_exit ? "true" : "false",
        total_uptime,
        WiFi.status() == WL_CONNECTED ? "true" : "false",
        WiFi.RSSI(),
        WiFi.localIP().toString().c_str(),
        MDNS_HOSTNAME);
    httpServer.send(200, "application/json", buf);
}

void initThreads() {
    xTaskCreatePinnedToCore(
        taskHeartBeat,
        "TaskHeartBeat",
        1024,
        NULL,
        4,
        NULL,
        CPU_0
    );

    xTaskCreatePinnedToCore(
        taskWifiWatchdog,
        "TaskWifiWatchdog",
        3072,               // HTTPClient/WiFi reconnect needs more headroom than the heartbeat
        NULL,
        3,
        NULL,
        CPU_0
    );

    xTaskCreatePinnedToCore(
        taskBoomgate,
        "TaskBoomgate",
        2048,
        NULL,
        4,
        NULL,
        CPU_1
    );

    xTaskCreatePinnedToCore(
        taskSensors,
        "TaskSensors",
        3072,               // now reads two sensors and may fire an HTTPClient request
        NULL,
        4,
        NULL,
        CPU_0
    );
}

void taskHeartBeat(void *pvParameters) {
    (void) pvParameters;

    uint32_t last_tick = 0;
    bool     led_state = false;

    pinMode(LED_INDICATOR, OUTPUT);

    for (;;) {
        if ((uint32_t)(millis() - last_tick) > 999) {
            led_state = !led_state;
            total_uptime++;

            digitalWrite(LED_INDICATOR, led_state);

            last_tick = millis();
        }

        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

void taskWifiWatchdog(void *pvParameters) {
    (void) pvParameters;

    bool was_connected = (WiFi.status() == WL_CONNECTED);

    for (;;) {
        bool is_connected = (WiFi.status() == WL_CONNECTED);

        if (!is_connected) {
            Serial.println("[WIFI] Disconnected - reconnecting...");
            WiFi.disconnect();
            if (USE_STATIC_IP) {
                WiFi.config(STATIC_IP, STATIC_GATEWAY, STATIC_SUBNET, STATIC_DNS);
            }
            WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        } else if (is_connected && !was_connected) {
            // Fresh reconnect: the mDNS responder can go stale across a WiFi drop,
            // so re-announce it once the link is back.
            Serial.println("[WIFI] Reconnected - re-registering mDNS");
            setupMdns();
        }

        was_connected = is_connected;
        vTaskDelay(pdMS_TO_TICKS(WIFI_WATCHDOG_INTERVAL_MS));
    }
}

/*
 * Drives the boom servo based on boomgate_status:
 *   GATE_IDLE  (0) - nothing to do
 *   GATE_OPEN  (1) - set by the /open_gate HTTP handler (terminal Pi's decision)
 *   GATE_CLOSE (2) - set by the /close_gate handler, or automatically once the
 *                    exit sensor sees the vehicle has cleared the gate.
 * The gate no longer opens itself from sensor readings - only via command.
 *
 * This is the single choke point that actually moves the servo, so it's also
 * where the presence interlock lives: a close is refused (and re-idled, not
 * left pending) if either sensor currently sees a vehicle, regardless of who
 * asked for the close - the automatic exit-clear path, a manual /close_gate
 * call, or anything else added later. This makes /close_gate safe by
 * construction instead of relying on every caller to check presence itself.
 */
void taskBoomgate(void *pvParameters) {
    (void) pvParameters;

    boomServo.attach(SERVO_PIN);
    boomServo.write(CLOSED_ANGLE); // start closed

    uint32_t last_trigger = 0;
    uint32_t last_defer_log = 0;

    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(10));

        if ((uint32_t)(millis() - last_trigger) < GATE_TRIGGER_COOLDOWN_MS) {
            continue;
        }

        if (boomgate_status == GATE_OPEN) {
            boomServo.write(OPEN_ANGLE);
            Serial.println("[GATE] Opened");
            gate_is_open = true;
            boomgate_status = GATE_IDLE;
            last_trigger = millis();
        } else if (boomgate_status == GATE_CLOSE) {
            // In CLOSE_ON_ENTRY_CLEAR test mode, the exit sensor is deliberately not
            // part of this flow at all - but it still keeps producing readings, and a
            // stuck/false "present" from it was silently killing every close request
            // (this check has no retry - a single bad reading at the wrong instant
            // drops the close attempt for good). Since exit isn't trusted or used for
            // anything else in this mode, don't let it block the close either.
            bool exitBlocksClose = vehicle_at_exit && !CLOSE_ON_ENTRY_CLEAR;
            if (vehicle_at_entry || exitBlocksClose) {
                boomgate_status = GATE_IDLE;
                if ((uint32_t)(millis() - last_defer_log) > 999) {
                    Serial.println("[GATE] Close deferred - vehicle still present");
                    last_defer_log = millis();
                }
            } else {
                boomServo.write(CLOSED_ANGLE);
                Serial.println("[GATE] Closed");
                gate_is_open = false;
                boomgate_status = GATE_IDLE;
                last_trigger = millis();
            }
        }
    }
}

/*
 * Entry sensor: on presence (rising edge), notify the terminal Pi so it can begin
 * plate recognition. Does NOT open the gate directly - that's the terminal Pi's call.
 * On clear (confirmed), also requests a close if CLOSE_ON_ENTRY_CLEAR is set (see
 * main.h) - a demo/test-mode convenience for exercising the full cycle without the
 * exit sensor, subject to the same presence interlock as the exit-triggered close.
 *
 * Exit sensor: once the gate is open, it's meant to STAY open for as long as a
 * vehicle is anywhere in the passage - a detection on either sensor while open is
 * expected, not a reason to close. Closing only happens once the exit sensor confirms
 * the vehicle has genuinely moved past it: it has to read clear continuously for
 * EXIT_CLEAR_CONFIRM_MS before that's trusted, since a single noisy sample isn't
 * enough (the exit sensor has been observed flickering present/absent rapidly when
 * something merely sits near the threshold distance - a raw single-sample edge would
 * false-trigger a close on that noise instead of a real pass-through).
 *
 * Only a genuine in-range-or-beyond echo counts towards that clear-confirm window -
 * a pulseIn timeout (no echo: bad reflection angle, loose wire, dead sensor) is
 * indistinguishable from "vehicle far away" at the single-reading level, so it must
 * NOT be allowed to advance the debounce. Otherwise a dropout while a vehicle is
 * still sitting under the gate would look identical to it driving away, and the
 * gate would auto-close on top of it. (The actual close is also re-checked against
 * live presence in taskBoomgate right before the servo moves, as a second layer.)
 */
void taskSensors(void *pvParameters) {
    (void) pvParameters;

    pinMode(TRIG_ENTRY, OUTPUT);
    pinMode(ECHO_ENTRY, INPUT);
    pinMode(TRIG_EXIT, OUTPUT);
    pinMode(ECHO_EXIT, INPUT);

    uint32_t last_debug_print = 0;
    uint32_t last_fault_log = 0;
    uint32_t last_entry_fault_log = 0;
    uint32_t exit_clear_since = 0; // 0 = not currently in a pending "clear" window
    uint32_t exit_present_since = 0; // 0 = not currently in a pending "arrived" window
    uint32_t entry_present_since = 0; // 0 = not currently in a pending "arrived" window
    uint32_t entry_clear_since = 0; // 0 = not currently in a pending "clear" window

    for (;;) {
        long distEntry = readDistanceCm(TRIG_ENTRY, ECHO_ENTRY);
        bool validEntry = (distEntry > 0); // false = pulseIn timeout, not a trustworthy "clear"
        bool presentEntry = (validEntry && distEntry < DISTANCE_THRESHOLD_CM);
        bool confirmedClearEntry = (validEntry && !presentEntry);

        if (presentEntry) {
            entry_clear_since = 0; // any presence reading cancels a pending clear-confirmation
            if (!vehicle_at_entry) {
                if (entry_present_since == 0) {
                    entry_present_since = millis(); // start the confirm window
                } else if ((uint32_t)(millis() - entry_present_since) >= ENTRY_PRESENT_CONFIRM_MS) {
                    vehicle_at_entry = true;
                    entry_present_since = 0;
                    Serial.println("[ENTRY] Vehicle detected");
                    notifyTerminalPiVehicleDetected();
                }
            }
        } else {
            entry_present_since = 0; // any non-present reading cancels a pending arrival-confirmation
            if (vehicle_at_entry) {
                if (confirmedClearEntry) {
                    if (entry_clear_since == 0) {
                        entry_clear_since = millis(); // start the confirm window
                    } else if ((uint32_t)(millis() - entry_clear_since) >= ENTRY_CLEAR_CONFIRM_MS) {
                        vehicle_at_entry = false;
                        entry_clear_since = 0;
                        Serial.println("[ENTRY] Vehicle cleared entry zone");
                        if (pendingVehicleLeftNotify) {
                            pendingVehicleLeftNotify = false;
                            Serial.println("[ENTRY] Sending deferred vehicle-left notification now that entry is clear");
                            notifyTerminalPiVehicleLeft();
                        }
                        if (CLOSE_ON_ENTRY_CLEAR) {
                            // Test mode: the exit sensor's reset call is fully disabled
                            // (see the exit block below), and it was the ONLY thing that
                            // ever cleared detect_car on the terminal Pi. Without this,
                            // detect_car stays 1 forever after the first trigger, so
                            // lpr_file_post.sh/LPR5Lite just keep re-authorizing the same
                            // plate on their own internal timer and reopening the gate
                            // with nobody there - observed live (gate reopened 12s after
                            // closing, entry empty the whole time). Reset it here instead,
                            // tied to the same entry-clear edge that closes the gate.
                            notifyTerminalPiResetFromEntryClear();
                            if (gate_is_open) {
                                boomgate_status = GATE_CLOSE;
                            }
                        }
                    }
                } else {
                    // Sensor dropout while a vehicle is still logically present at entry -
                    // don't let this count as progress towards "clear", just wait it out.
                    entry_clear_since = 0;
                    if ((uint32_t)(millis() - last_entry_fault_log) > EXIT_SENSOR_FAULT_LOG_INTERVAL_MS) {
                        Serial.println("[ENTRY] WARNING: no echo while vehicle present - sensor dropout?");
                        last_entry_fault_log = millis();
                    }
                }
            }
        }

        long distExit = readDistanceCm(TRIG_EXIT, ECHO_EXIT);
        bool validExit = (distExit > 0); // false = pulseIn timeout, not a trustworthy "clear"
        bool presentExit = (validExit && distExit < DISTANCE_THRESHOLD_CM);
        bool confirmedClearExit = (validExit && !presentExit);

        if (presentExit) {
            exit_clear_since = 0; // any presence reading cancels a pending clear-confirmation
            if (!vehicle_at_exit) {
                if (exit_present_since == 0) {
                    exit_present_since = millis(); // start the confirm window
                } else if ((uint32_t)(millis() - exit_present_since) >= EXIT_PRESENT_CONFIRM_MS) {
                    vehicle_at_exit = true;
                    exit_present_since = 0;
                    Serial.println("[EXIT] Vehicle entered exit zone");
                }
            }
        } else {
            exit_present_since = 0; // any non-present reading cancels a pending arrival-confirmation
            if (vehicle_at_exit) {
                if (confirmedClearExit) {
                    if (exit_clear_since == 0) {
                        exit_clear_since = millis(); // start the confirm window
                    } else if ((uint32_t)(millis() - exit_clear_since) >= EXIT_CLEAR_CONFIRM_MS) {
                        vehicle_at_exit = false;
                        exit_clear_since = 0;
                        Serial.println("[EXIT] Vehicle confirmed clear of exit zone");
                        if (CLOSE_ON_ENTRY_CLEAR) {
                            // Test mode: exit sensor is irrelevant here by design - entry
                            // alone drives the whole cycle. Still tracked above (visible in
                            // /status for diagnostics) but must not drive any side effects,
                            // or a flickering/stuck exit reading could reset an in-progress
                            // LPR cycle or fire a redundant close behind entry's back.
                            Serial.println("[EXIT] Ignoring clear event - CLOSE_ON_ENTRY_CLEAR test mode, exit sensor not part of this flow");
                        } else if (!vehicle_at_entry) {
                            notifyTerminalPiVehicleLeft();
                            if (gate_is_open) {
                                boomgate_status = GATE_CLOSE;
                            }
                        } else {
                            // Don't just drop this - defer it. vehicle_at_entry can flip
                            // true again shortly after (e.g. this same car crossing back
                            // over the entry sensor in reverse, as happens every cycle on
                            // this single-lane demo track), and a dropped notify left the
                            // terminal Pi's LPR cycle stuck thinking the car never left,
                            // which kept re-forcing the gate open on its own retry timer -
                            // defeating the vehicle_inside_flag re-entry block entirely.
                            pendingVehicleLeftNotify = true;
                            Serial.println("[EXIT] Deferring terminal-Pi reset - vehicle still at entry, will resend once entry clears");
                            if (gate_is_open) {
                                boomgate_status = GATE_CLOSE;
                            }
                        }
                    }
                } else {
                    // Sensor dropout while a vehicle is still logically present at exit -
                    // don't let this count as progress towards "clear", just wait it out.
                    exit_clear_since = 0;
                    if ((uint32_t)(millis() - last_fault_log) > EXIT_SENSOR_FAULT_LOG_INTERVAL_MS) {
                        Serial.println("[EXIT] WARNING: no echo while vehicle present - sensor dropout? holding gate open");
                        last_fault_log = millis();
                    }
                }
            }
        }

        // Temporary diagnostic - raw readings every ~1s, not just on edges, to tell
        // "disconnected/floating pin" apart from "connected but timing/threshold issue".
        if ((uint32_t)(millis() - last_debug_print) > 999) {
            Serial.printf("[RAW] entry=%ldcm exit=%ldcm\n", distEntry, distExit);
            last_debug_print = millis();
        }

        vTaskDelay(pdMS_TO_TICKS(SENSOR_POLL_INTERVAL_MS));
    }
}

static void callTerminalPi(const char *url, const char *logTag) {
    if (!ENABLE_TERMINAL_PI_NOTIFY) {
        return;
    }

    if (WiFi.status() != WL_CONNECTED) {
        Serial.printf("[%s] Skipped - WiFi not connected\n", logTag);
        return;
    }

    HTTPClient http;
    http.begin(url);
    http.setTimeout(TERMINAL_PI_NOTIFY_TIMEOUT_MS);
    int code = http.GET();

    if (code > 0) {
        Serial.printf("[%s] Terminal Pi -> HTTP %d\n", logTag, code);
    } else {
        Serial.printf("[%s] Terminal Pi call FAILED: %s\n", logTag, http.errorToString(code).c_str());
    }

    http.end();
}

void notifyTerminalPiVehicleDetected() {
    callTerminalPi(TERMINAL_PI_NOTIFY_URL, "ENTRY");
}

void notifyTerminalPiVehicleLeft() {
    callTerminalPi(TERMINAL_PI_RESET_URL, "EXIT");
}

void notifyTerminalPiResetFromEntryClear() {
    callTerminalPi(TERMINAL_PI_RESET_URL, "ENTRY-RESET");
}

// Returns distance in cm, or -1 if the sensor timed out (no echo / out of range).
long readDistanceCm(int trigPin, int echoPin) {
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);

    unsigned long duration = pulseIn(echoPin, HIGH, SENSOR_ECHO_TIMEOUT_US);
    if (duration == 0) {
        return -1;
    }

    return (long)(duration * 0.034 / 2);
}
