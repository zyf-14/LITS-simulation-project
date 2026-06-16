#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <WiFiServer.h>
#include <WiFiClient.h>
#include <ESP32Servo.h>
#include "config.h"

// ===== SERVO CONFIG =====
#define SERVO_GPIO   13
#define OPEN_ANGLE   100
#define CLOSE_ANGLE  180

Servo myServo;

// ===== GATE ID =====
#define GATE_ID "B"

// ===== GPIO PINS =====
#define TRIG_1        2
#define ECHO_1        5
#define TRIG_2        18
#define ECHO_2        15
#define LED_INDICATOR 4

// ===== PI SERVER =====
#define PI_DETECT_URL "http://" PI_SERVER_IP "/detect_car.php"

// ===== TIMING =====
const unsigned long OPEN_RETRY_INTERVAL = 10000;  // ms between re-open attempts
const int           LOST_COUNT_THRESHOLD = 10;    // poll cycles before closing gate

// ===== GLOBALS =====
WebServer   server(80);
WiFiServer  telnetServer(23);
WiFiClient  telnetClient;

bool sensor1_detected      = false;
bool sensor2_detected      = false;
bool gate_open             = false;
bool gate_permission_granted = false;
bool printed_vehicle_present = false;
bool any_detected          = false;
bool last_sent_status      = false;

unsigned long last_open_retry = 0;

// ===== HELPERS =====

void telnetPrint(const String& msg) {
  Serial.println(msg);
  if (telnetClient && telnetClient.connected()) {
    telnetClient.println(msg);
  }
}

long getDistance(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH); delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH, 30000);
  return duration * 0.034 / 2;
}

// ===== PI COMMUNICATION =====

void notifyPiVehicleStatus(bool detected) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String(PI_DETECT_URL) + "?detect_car=" + (detected ? "1" : "0");
  http.begin(url);
  int code = http.GET();
  telnetPrint(code > 0
    ? "[Pi] Notified: " + url + " | HTTP " + String(code)
    : "[Pi] Notify failed: " + url);
  http.end();
}

bool checkPermissionFromPi() {
  if (WiFi.status() != WL_CONNECTED) return false;

  HTTPClient http;
  String url = String(PI_DETECT_URL) + "?detect_car=1";
  http.begin(url);
  int code = http.GET();

  if (code == 200) {
    String response = http.getString();
    http.end();
    if (response == "OPEN") {
      telnetPrint("[Pi] Permission granted — OPEN");
      return true;
    }
    telnetPrint("[Pi] Permission denied — WAIT");
    return false;
  }

  telnetPrint("[Pi] Permission check failed. HTTP " + String(code));
  http.end();
  return false;
}

// ===== FREERTOS TASKS =====

void taskHeartbeat(void* pv) {
  pinMode(LED_INDICATOR, OUTPUT);
  while (true) {
    digitalWrite(LED_INDICATOR, !digitalRead(LED_INDICATOR));
    vTaskDelay(1000 / portTICK_PERIOD_MS);
  }
}

void taskSensor(void* pv) {
  while (true) {
    long d1 = getDistance(TRIG_1, ECHO_1);
    long d2 = getDistance(TRIG_2, ECHO_2);
    sensor1_detected = (d1 > 1 && d1 < 10);
    sensor2_detected = (d2 > 1 && d2 < 10);
    vTaskDelay(200 / portTICK_PERIOD_MS);
  }
}

void taskBoomGate(void* pv) {
  static bool asked_permission = false;
  static int  lost_count       = 0;

  while (true) {
    any_detected = sensor1_detected || sensor2_detected;

    // Notify Pi whenever detection state changes
    if (any_detected != last_sent_status) {
      notifyPiVehicleStatus(any_detected);
      last_sent_status = any_detected;
    }

    // Ask Pi for permission once per detection event
    if (any_detected && !gate_open && !asked_permission) {
      telnetPrint("[Gate] Vehicle detected — requesting permission...");
      gate_permission_granted = checkPermissionFromPi();
      asked_permission = true;
    }

    // Gate opens via HTTP /open_gate endpoint (triggered by Pi server).
    // See setup() below — the Pi calls /open_gate after verifying the vehicle.

    // Keep gate held open while vehicle is still present
    if (gate_open && any_detected && millis() - last_open_retry > OPEN_RETRY_INTERVAL) {
      myServo.write(OPEN_ANGLE);
      last_open_retry = millis();
      telnetPrint("[Gate] Vehicle still present — re-holding open");
    }

    if (gate_open && any_detected && !printed_vehicle_present) {
      telnetPrint("[Gate] Vehicle under gate");
      printed_vehicle_present = true;
    }

    // Close gate after vehicle has been absent for LOST_COUNT_THRESHOLD cycles
    if (gate_open && !any_detected) {
      lost_count++;
      if (lost_count >= LOST_COUNT_THRESHOLD) {
        myServo.write(CLOSE_ANGLE);
        gate_open             = false;
        gate_permission_granted = false;
        printed_vehicle_present = false;
        asked_permission      = false;
        lost_count            = 0;
        telnetPrint("[Gate] Vehicle gone — gate closed");
      }
    } else {
      lost_count = 0;
    }

    vTaskDelay(300 / portTICK_PERIOD_MS);
  }
}

// ===== SETUP =====

void setup() {
  Serial.begin(115200);

  pinMode(TRIG_1, OUTPUT); pinMode(ECHO_1, INPUT);
  pinMode(TRIG_2, OUTPUT); pinMode(ECHO_2, INPUT);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WiFi] Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\n[WiFi] Connected: " + WiFi.localIP().toString());

  myServo.setPeriodHertz(50);
  myServo.attach(SERVO_GPIO, 500, 2500);
  myServo.write(CLOSE_ANGLE);

  // HTTP endpoint — Pi calls this to open the gate after granting permission
  server.on("/open_gate", HTTP_GET, []() {
    myServo.write(OPEN_ANGLE);
    gate_open             = true;
    gate_permission_granted = true;
    printed_vehicle_present = false;
    last_open_retry       = millis();
    server.send(200, "text/plain", "Gate opened");
    telnetPrint("[Gate] Opened via /open_gate");
  });

  server.begin();
  Serial.println("[HTTP] Server running");

  telnetServer.begin();
  telnetServer.setNoDelay(true);
  Serial.println("[Telnet] Ready on port 23");

  xTaskCreatePinnedToCore(taskHeartbeat, "Heartbeat", 1024, NULL, 1, NULL, 0);
  xTaskCreatePinnedToCore(taskSensor,    "Sensor",    2048, NULL, 1, NULL, 0);
  xTaskCreatePinnedToCore(taskBoomGate,  "BoomGate",  4096, NULL, 1, NULL, 1);
}

// ===== LOOP =====

void loop() {
  server.handleClient();

  if (telnetServer.hasClient()) {
    if (telnetClient) telnetClient.stop();
    telnetClient = telnetServer.available();
    telnetPrint("[Telnet] Client connected");
  }

  delay(10);
}
