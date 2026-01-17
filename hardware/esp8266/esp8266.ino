#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ArduinoJson.h>

// =================== WiFi Config ===================
static const char* WIFI_SSID = "Golden’s iPhone";
static const char* WIFI_PASS = "winners!";
static const char* HOSTNAME  = "handwashled";

ESP8266WebServer server(80);

// =================== Debug ===================
// Set true to print every received signal + decisions.
static const bool DEBUG_SIGNALS = true;

// Optional: rate-limit identical logs (prevents Serial spam if Pi sends frequently)
static const uint32_t DEBUG_MIN_INTERVAL_MS = 50; // 0 to disable
String lastDebugLine = "";
uint32_t lastDebugMs = 0;

enum class LedState : uint8_t { IDLE, CURRENT, COMPLETED };

static const char* stateToStr(uint8_t s) {
  switch ((LedState)s) {
    case LedState::IDLE: return "IDLE";
    case LedState::CURRENT: return "CURRENT";
    case LedState::COMPLETED: return "COMPLETED";
    default: return "?";
  }
}

static void debugLog(const String& line) {
  if (!DEBUG_SIGNALS) return;

  uint32_t now = millis();
  if (DEBUG_MIN_INTERVAL_MS > 0) {
    if (line == lastDebugLine && (now - lastDebugMs) < DEBUG_MIN_INTERVAL_MS) {
      return;
    }
  }
  lastDebugLine = line;
  lastDebugMs = now;
  Serial.println(line);
}

// =================== Step → Pin Mapping ===================
static const int8_t STEP_TO_PIN[8] = {
  -1,   // 0 unused
  -1,   // step 1 unused
  D0,   // step 2
  D1,   // step 3
  D4,   // step 4
  D5,   // step 5
  D6,   // step 6
  D7    // step 7
};

static const uint32_t BLINK_ON_MS  = 500;
static const uint32_t BLINK_OFF_MS = 500;

struct StepLed {
  LedState state = LedState::IDLE;
  bool completed = false;     // latch
  bool level = false;         // logical LED state (on/off) for blink loop
};

StepLed steps[8];
int8_t currentStep = -1;
uint32_t blinkStartMs = 0;   // phase anchor: only set when entering CURRENT

static void writeLed(uint8_t step, bool on) {
  int8_t pin = STEP_TO_PIN[step];
  if (pin < 0) return;
  digitalWrite(pin, on ? HIGH : LOW);
  steps[step].level = on;
}

static void applyImmediate(uint8_t step) {
  // COMPLETED is solid ON
  if (steps[step].completed || steps[step].state == LedState::COMPLETED) {
    writeLed(step, true);
    return;
  }

  // CURRENT: no phase changes here
  if (steps[step].state == LedState::CURRENT) {
    return;
  }

  // IDLE is OFF
  writeLed(step, false);
}

static void clearCurrent() {
  if (currentStep >= 2 && currentStep <= 7) {
    uint8_t s = (uint8_t)currentStep;
    if (!steps[s].completed) {
      steps[s].state = LedState::IDLE;
      applyImmediate(s);
    }
  }
  currentStep = -1;
}

static void setCurrentStep(uint8_t step) {
  if (step < 2 || step > 7) return;

  // If already current + CURRENT, do nothing (do NOT reset phase)
  if (currentStep == (int8_t)step && steps[step].state == LedState::CURRENT) {
    debugLog("[SIGNAL] CURRENT no-op (already current) step=" + String(step));
    return;
  }

  // Clear previous current step (turn it off unless completed)
  if (currentStep >= 2 && currentStep <= 7 && currentStep != (int8_t)step) {
    uint8_t prev = (uint8_t)currentStep;
    if (!steps[prev].completed) {
      steps[prev].state = LedState::IDLE;
      writeLed(prev, false);
      debugLog("[STATE] cleared previous CURRENT step=" + String(prev));
    } else {
      debugLog("[STATE] previous CURRENT step=" + String(prev) + " was completed (kept solid)");
    }
  }

  currentStep = (int8_t)step;
  steps[step].state = LedState::CURRENT;

  // Start blink phase exactly once on transition
  blinkStartMs = millis();

  debugLog("[STATE] set CURRENT step=" + String(step) + " blinkStartMs=" + String(blinkStartMs));
}

static bool parseState(const String& s, LedState &out) {
  if (s == "IDLE")      { out = LedState::IDLE; return true; }
  if (s == "CURRENT")   { out = LedState::CURRENT; return true; }
  if (s == "COMPLETED") { out = LedState::COMPLETED; return true; }
  return false;
}

static void resetSession() {
  clearCurrent();
  for (uint8_t i = 2; i <= 7; i++) {
    steps[i].state = LedState::IDLE;
    steps[i].completed = false;
    steps[i].level = false;
    writeLed(i, false);
  }
  debugLog("[STATE] session reset");
}

// =================== HTTP ===================
static void handleHealth() {
  StaticJsonDocument<256> doc;
  doc["ok"] = true;
  doc["ip"] = WiFi.localIP().toString();
  doc["rssi"] = WiFi.RSSI();
  doc["currentStep"] = currentStep;

  JsonArray completed = doc.createNestedArray("completed");
  for (uint8_t i = 2; i <= 7; i++) {
    if (steps[i].completed) completed.add(i);
  }

  String out;
  serializeJson(doc, out);
  server.send(200, "application/json", out);
}

static void handleReset() {
  resetSession();
  server.send(200, "application/json", "{\"ok\":true}");
}

static void handleSignal() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed");
    return;
  }

  const String body = server.arg("plain");
  if (body.length() == 0) {
    server.send(400, "text/plain", "Missing JSON body");
    return;
  }

  StaticJsonDocument<256> doc;
  auto err = deserializeJson(doc, body);
  if (err) {
    server.send(400, "text/plain", "Invalid JSON");
    return;
  }

  if (!doc.containsKey("step") || !doc.containsKey("state")) {
    server.send(400, "text/plain", "Missing step/state");
    return;
  }

  int step = doc["step"].as<int>();
  String stateStr = doc["state"].as<String>();

  if (step < 2 || step > 7) {
    server.send(400, "text/plain", "Step must be 2..7 for this LED layout");
    return;
  }

  LedState state;
  if (!parseState(stateStr, state)) {
    server.send(400, "text/plain", "State must be IDLE|CURRENT|COMPLETED");
    return;
  }

  uint8_t s = (uint8_t)step;

  // Log what arrived + some current internal state before we apply it
  debugLog(
    "[RX] step=" + String(step) +
    " state=" + String(stateStr) +
    " | currentStep=" + String(currentStep) +
    " stepState=" + String(stateToStr((uint8_t)steps[s].state)) +
    " completed=" + String(steps[s].completed ? "1" : "0")
  );

  if (state == LedState::COMPLETED) {
    steps[s].completed = true;
    steps[s].state = LedState::COMPLETED;

    // If it was blinking, stop
    if (currentStep == step) {
      currentStep = -1;
      debugLog("[STATE] COMPLETED stopped CURRENT for step=" + String(step));
    }

    // Solid ON
    writeLed(s, true);
    debugLog("[LED] step=" + String(step) + " -> SOLID ON (COMPLETED)");

  } else if (state == LedState::CURRENT) {
    // Never re-enter blink after completion
    if (!steps[s].completed) {
      setCurrentStep(s);  // idempotent; won't reset blinkStartMs if repeated
      debugLog("[LED] step=" + String(step) + " -> BLINK (CURRENT)");
    } else {
      // keep it solid
      writeLed(s, true);
      debugLog("[LED] step=" + String(step) + " CURRENT ignored (already completed) -> kept SOLID");
    }

  } else { // IDLE
    // If completed, ignore IDLE (keep solid)
    if (steps[s].completed) {
      writeLed(s, true);
      debugLog("[LED] step=" + String(step) + " IDLE ignored (completed) -> kept SOLID");
    } else {
      if (currentStep == step) {
        currentStep = -1;
        debugLog("[STATE] IDLE cleared CURRENT for step=" + String(step));
      }
      steps[s].state = LedState::IDLE;
      applyImmediate(s);
      debugLog("[LED] step=" + String(step) + " -> OFF (IDLE)");
    }
  }

  server.send(200, "application/json", "{\"ok\":true}");
}

void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println();
  Serial.println("ESP8266 Handwash LED starting...");
  Serial.print("ESP IP: ");
  Serial.println(WiFi.localIP());

  // Init pins
  for (uint8_t s = 2; s <= 7; s++) {
    int8_t pin = STEP_TO_PIN[s];
    if (pin >= 0) {
      pinMode(pin, OUTPUT);
      digitalWrite(pin, LOW);
    }
  }

  WiFi.mode(WIFI_STA);
  WiFi.hostname(HOSTNAME);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.printf("Connecting to WiFi: %s\n", WIFI_SSID);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print(".");
    if (millis() - start > 15000) {
      Serial.println("\nWiFi timeout, rebooting...");
      ESP.restart();
    }
  }

  Serial.println("\nWiFi connected.");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  server.on("/health", HTTP_GET, handleHealth);
  server.on("/reset", HTTP_POST, handleReset);
  server.on("/signal", HTTP_POST, handleSignal);
  server.begin();

  Serial.println("HTTP server ready on :80");
  resetSession();
}

void loop() {
  server.handleClient();

  // Blink CURRENT step at exactly 1 Hz, 50% duty (500ms on/500ms off)
  // Deterministic: based only on (millis - blinkStartMs), so repeated CURRENT packets can't speed it up.
  if (currentStep >= 2 && currentStep <= 7) {
    uint8_t s = (uint8_t)currentStep;

    if (!steps[s].completed && steps[s].state == LedState::CURRENT) {
      uint32_t phase = (millis() - blinkStartMs) % 1000;
      bool shouldBeOn = (phase < 500);

      if (steps[s].level != shouldBeOn) {
        writeLed(s, shouldBeOn);
        // Uncomment if you want VERY verbose timing logs:
        // debugLog("[BLINK] step=" + String(currentStep) + " phase=" + String(phase) + " -> " + String(shouldBeOn ? "ON" : "OFF"));
      }
    }
  }
}