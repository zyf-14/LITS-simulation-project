#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <WiFiServer.h>
#include <WiFiClient.h>
#include <ESP32Servo.h>

//TO CHECK IF WORKING RUN THIS FILE :(tail -f /dev/shm/lpr_file_post.log)
// PASSWORD FOR LOGIN INTO PI = LiTS1234
// ===== SERVO CONFIG =====
#define SERVO_GPIO 13
Servo myServo;
int open_angle = 100;
int close_angle = 180;

// ===== CONFIG =====
#define GATE_ID "B"
const char* ssid = "LiTS2";
const char* password = "BondBond12$";

// ===== GPIO CONFIG =====
#define TRIG_1 2
#define ECHO_1 5
#define TRIG_2 18
#define ECHO_2 15
#define LED_INDICATOR 4

// ===== Globals =====
WebServer server(80);
WiFiServer telnetServer(23);
WiFiClient telnetClient;

bool sensor1_detected = false;
bool sensor2_detected = false;
bool gate_open = false;
bool gate_permission_granted = false;
bool printed_vehicle_present = false;
bool any_detected = false;
bool last_sent_status = false;

unsigned long last_open_retry = 0;
const unsigned long open_retry_interval = 10000;

// ===== DEBUG PRINT =====
void telnetPrint(const String& msg) {
  Serial.println(msg);
  if (telnetClient && telnetClient.connected()) {
    telnetClient.println(msg);
  }
}

// ===== ULTRASONIC FUNCTION =====
long getDistance(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW); delayMicroseconds(2);
  digitalWrite(trigPin, HIGH); delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH, 30000);
  return duration * 0.034 / 2;
}

// ===== NOTIFY PI OF VEHICLE STATUS =====
void notifyPiVehicleStatus(bool detected) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    String url = "http://192.168.183.70/detect_car.php?detect_car=" + String(detected ? "1" : "0");
    http.begin(url);
    int responseCode = http.GET();

    if (responseCode > 0) {
      telnetPrint("📡 Sent to Pi: " + url + " | Code: " + String(responseCode));
    } else {
      telnetPrint("❌ Failed to send GET: " + url);
    }
    http.end();
  }
}

// ===== ASK PI IF GATE CAN OPEN =====
bool checkPermissionFromPi() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    String url = "http://192.168.183.70/detect_car.php?detect_car=1";
    http.begin(url);
    int responseCode = http.GET();

    if (responseCode == 200) {
      String response = http.getString();
      http.end();
      if (response == "OPEN") {
        telnetPrint("✅ Pi says: OPEN the gate!");
        return true;
      } else {
        telnetPrint("⏳ Pi says: WAIT or DENY");
      }
    } else {
      telnetPrint("❌ GET failed. Code: " + String(responseCode));
    }
    http.end();
  }
  return false;
}

// ===== HEARTBEAT =====
void taskHeartBeat(void* pv) {
  pinMode(LED_INDICATOR, OUTPUT);
  while (true) {
    digitalWrite(LED_INDICATOR, !digitalRead(LED_INDICATOR));
    vTaskDelay(1000 / portTICK_PERIOD_MS);
  }
}

// ===== SENSOR TASK =====
void sensorTask(void* pv) {
  while (true) {
    long d1 = getDistance(TRIG_1, ECHO_1);
    long d2 = getDistance(TRIG_2, ECHO_2);
    sensor1_detected = (d1 > 1 && d1 < 10);
    sensor2_detected = (d2 > 1 && d2 < 10);
    vTaskDelay(200 / portTICK_PERIOD_MS);
  }
}

// ===== BOOM GATE LOGIC =====
void boomLogic(void* pv) {
  static int lost_count = 0;

  while (true) {
    any_detected = sensor1_detected || sensor2_detected;

    // ✅ ALWAYS notify Pi when status changes
    if (any_detected != last_sent_status) {
      notifyPiVehicleStatus(any_detected);
      last_sent_status = any_detected;
    }

    // 🔓 Ask permission once when detection starts
    static bool asked_permission = false;
    if (any_detected && !gate_open && !asked_permission) {
      telnetPrint("🚗 Detected! Asking Pi...");
      gate_permission_granted = checkPermissionFromPi();
      asked_permission = true;
    }

    // ✅ Open gate if allowed
    // if (any_detected && !gate_open && gate_permission_granted) {
    //   telnetPrint("🟢 Permission granted. Opening gate...");
    //   myServo.write(open_angle);
    //   gate_open = true;
    //   last_open_retry = millis();
    // }

    // ♻️ Reopen every 10s if still present
    if (gate_open && any_detected && millis() - last_open_retry > open_retry_interval) {
      telnetPrint("🔁 Still detected. Re-opening.");
      myServo.write(open_angle);
      last_open_retry = millis();
    }

    if (gate_open && any_detected && !printed_vehicle_present) {
      telnetPrint("🚙 Vehicle still there...");
      printed_vehicle_present = true;
    }

    // 🔒 Close gate after 3s of absence
    if (gate_open && !any_detected) {
      lost_count++;
      if (lost_count >= 10) {
        telnetPrint("🔒 Vehicle gone. Closing gate.");
        myServo.write(close_angle);
        gate_open = false;
        gate_permission_granted = false;
        printed_vehicle_present = false;
        asked_permission = false;
        lost_count = 0;
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

  WiFi.begin(ssid, password);
  Serial.print("🌐 Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\n✅ WiFi Connected: " + WiFi.localIP().toString());

  myServo.setPeriodHertz(50);
  myServo.attach(SERVO_GPIO, 500, 2500);
  myServo.write(close_angle);

  telnetServer.begin(); telnetServer.setNoDelay(true);
  Serial.println("📡 Telnet ready");

  server.on("/open_gate", HTTP_GET, []() {
    myServo.write(open_angle);
    gate_open = true;
    gate_permission_granted = true;
    printed_vehicle_present = false;
    last_open_retry = millis();
    server.send(200, "text/plain", "🚀 Gate opened by GET");
    telnetPrint("🖥️ /open_gate called.");
  });

  server.begin();
  Serial.println("🌍 HTTP server running");

  xTaskCreatePinnedToCore(taskHeartBeat, "Heartbeat", 1024, NULL, 1, NULL, 0);
  xTaskCreatePinnedToCore(sensorTask, "Sensor", 2048, NULL, 1, NULL, 0);
  xTaskCreatePinnedToCore(boomLogic, "Logic", 4096, NULL, 1, NULL, 1);
}

// ===== LOOP =====
void loop() {
  server.handleClient();
  if (telnetServer.hasClient()) {
    if (telnetClient) telnetClient.stop();
    telnetClient = telnetServer.available();
    telnetPrint("📲 Telnet client connected!");
  }
  delay(10);
}
