// Prueba de la cadena de LEDs rojos interiores (mismo pin y circuito que firmware/eyes):
// GPIO32 -> 1 k -> base KSP2222A; cada LED con su 220 ohm a 5 V; pin alto = encendido.
// Comandos por serial (115200, fin de linea Newline):
//   G <0..255>  brillo fijo (al arrancar: 255)
//   P           latido lento
//   S           parpadeo rapido (estroboscopio)
//   R           rampa: sube y baja el brillo para ver el rango completo
//   H [bpm]     latido de corazon "pum-pum ... pum-pum" (por defecto 70 bpm)
//   0           apagar
#define PIN_LEDS 32

enum Mode { FIXED, PULSE, STROBE, RAMP, HEART } mode = FIXED;
int bpm = 70;
uint32_t heartStart = 0;

// destello: sube en 30 ms y se apaga exponencialmente
float flash(int32_t dt, float amp) {
  if (dt < 0) return 0;
  if (dt < 30) return amp * dt / 30.0;
  return amp * expf(-(dt - 30) / 70.0);
}

// "pum" fuerte, "pum" mas suave 200 ms despues, y silencio hasta el siguiente ciclo
int heartLevel(uint32_t now) {
  int32_t t = (now - heartStart) % (60000 / bpm);
  float a = flash(t, 1.0) + flash(t - 200, 0.7);
  return 6 + (int)(249 * (a > 1 ? 1 : a));
}

void level(int v) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_LEDS, constrain(v, 0, 255));
#else
  ledcWrite(0, constrain(v, 0, 255));
#endif
}

void setup() {
  Serial.begin(115200);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(PIN_LEDS, 5000, 8);
#else
  ledcSetup(0, 5000, 8);
  ledcAttachPin(PIN_LEDS, 0);
#endif
  level(255);
  delay(500);
  Serial.println("LEDs rojos al 100%. Comandos: 'G v' P S R 'H bpm' 0");
}

void handleSerial() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  line.toUpperCase();
  if (line.startsWith("G ")) {
    mode = FIXED;
    int v = line.substring(2).toInt();
    level(v);
    Serial.printf("Brillo %d\n", constrain(v, 0, 255));
  } else if (line == "P") {
    mode = PULSE;
    Serial.println("Latido");
  } else if (line == "S") {
    mode = STROBE;
    Serial.println("Estroboscopio");
  } else if (line == "R") {
    mode = RAMP;
    Serial.println("Rampa");
  } else if (line == "H" || line.startsWith("H ")) {
    if (line.length() > 2) bpm = constrain(line.substring(2).toInt(), 30, 180);
    mode = HEART;
    heartStart = millis();
    Serial.printf("Latido %d bpm\n", bpm);
  } else if (line == "0") {
    mode = FIXED;
    level(0);
    Serial.println("Apagado");
  } else if (line.length()) {
    Serial.println("Comandos: 'G v' P S R 'H bpm' 0");
  }
}

void loop() {
  handleSerial();
  uint32_t now = millis();
  if (mode == PULSE) {
    level(10 + (int)((sinf(now / 600.0) + 1) / 2 * 245));
  } else if (mode == STROBE) {
    level((now / 60) % 2 ? 255 : 0);
  } else if (mode == HEART) {
    level(heartLevel(now));
  } else if (mode == RAMP) {
    int t = (now / 8) % 512;  // ~4 s ida y vuelta
    level(t < 256 ? t : 511 - t);
  }
  delay(10);
}
