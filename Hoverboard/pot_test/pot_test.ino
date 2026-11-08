// Prueba de bancada: potenciometro -> ESP32 -> placa del hoverboard (firmware Gen2.x REMOTE_UARTBUS, SLAVE_ID 0).
// SOLO con la rueda en el aire, fuente limitada y manos lejos.
//
// Cableado (todo 3.3 V). TODO en el MISMO lado del DevKit de 30 pines (el de 3V3, GND, 15, 2, 4, 16, 17, 5, 18...):
//   3V3  -> potenciometro 10k, extremo 1
//   GND  -> potenciometro 10k, extremo 2  (y GND de la placa del hoverboard, mismo pin o el otro GND del DevKit)
//   GPIO4  <- cursor (el del medio) del potenciometro
//   GPIO16 (RX2) <- PB6 (TX) de la placa del hoverboard
//   GPIO17 (TX2) -> PB7 (RX) de la placa del hoverboard
//   Paro (opcional): GPIO18 a GND = parada inmediata (con pull-up interna; sin cable no hace nada)
//   No usar GPIO2, 12 y 15 (pines de arranque del ESP32).
//
// Uso: abre el monitor serie a 115200. Al arrancar hay que dejar el potenciometro en el CENTRO ~1 s
// para "armar"; mientras no este armado no se manda movimiento. Girar a un lado = adelante, al otro = atras.
// Centro = parado. Para detener: pot al centro, boton de paro, o desenchufar el ESP32 (la placa
// deshabilita el motor a los 500 ms sin tramas).
//
// Placa: "ESP32 Dev Module". No necesita bibliotecas externas.

const int POT_PIN = 4;                     // ADC2_CH0; vale porque no usamos WiFi
const int HOVER_RX = 16, HOVER_TX = 17;
const int ESTOP_PIN = 18;

const unsigned long HOVER_BAUD = 19200;
const uint8_t HOVER_ID = 1;                // 0 = placa derecha, 1 = placa izquierda (SLAVE_ID del firmware flasheado)
const uint8_t HOVER_STATE = 32;           // 32 = LEDs de bateria (igual que firmware/neck/neck.ino)

const int MAX_SPEED = 150;                 // 150 de 1000 = 15 % PWM maximo (limite de software)
const int DEADZONE = 250;                  // de 4095: ancho del "centro = parado"
const int ARM_BAND = 300;                  // el pot debe estar a +-300 del centro para armar
const unsigned long ARM_MS = 1000;
const unsigned long FRAME_MS = 25;         // 40 Hz

struct __attribute__((packed)) HoverCmd {
  uint8_t  start = '/';
  uint8_t  dataType = 1;
  uint8_t  slave = HOVER_ID;
  int16_t  speed = 0;
  int16_t  steer = 0;
  uint8_t  state = HOVER_STATE;
  uint8_t  stateSlave = HOVER_STATE;
  uint16_t crc = 0;
};

uint16_t crc16(const uint8_t *p, int n) {  // CRC-16/XMODEM (poly 0x1021, init 0), igual que neck.ino
  uint16_t crc = 0;
  while (n--) {
    crc ^= (uint16_t)*p++ << 8;
    for (int i = 0; i < 8; i++) crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : (crc << 1);
  }
  return crc;
}

void sendHover(int speed) {
  HoverCmd c;
  c.speed = speed;
  c.steer = 0;
  c.crc = crc16((uint8_t *)&c, sizeof(c) - 2);
  Serial2.write((uint8_t *)&c, sizeof(c));
}

// Telemetria de la placa: 0xABCD (CD AB), slave, int16 velocidad*100, uint16 V*100, int16 A*100, int32 odom, crc
float battV = -1, battA = -1;
uint32_t telemCount = 0;
void readTelemetry() {
  static uint8_t buf[15];
  static int pos = 0;
  while (Serial2.available()) {
    uint8_t b = Serial2.read();
    if (pos == 0 && b != 0xCD) continue;
    if (pos == 1 && b != 0xAB) { pos = 0; continue; }
    buf[pos++] = b;
    if (pos == 15) {
      pos = 0;
      uint16_t v = buf[5] | (buf[6] << 8);
      int16_t a = buf[7] | (buf[8] << 8);
      if (v < 6000) { battV = v / 100.0; battA = a / 100.0; telemCount++; }
    }
  }
}

int readPot() {                            // media de 16 lecturas, 0..4095
  long s = 0;
  for (int i = 0; i < 16; i++) s += analogRead(POT_PIN);
  return s / 16;
}

bool armed = false;
unsigned long centeredSince = 0, lastFrame = 0, lastPrint = 0;
int potCenter = 2048;

void setup() {
  Serial.begin(115200);
  Serial2.begin(HOVER_BAUD, SERIAL_8N1, HOVER_RX, HOVER_TX);
  pinMode(ESTOP_PIN, INPUT_PULLUP);
  analogReadResolution(12);
  delay(500);
  Serial.println("Deja el potenciometro en el CENTRO para armar...");
}

void loop() {
  unsigned long now = millis();
  readTelemetry();
  int raw = readPot();
  bool estop = (digitalRead(ESTOP_PIN) == LOW);

  if (!armed) {
    if (abs(raw - potCenter) < ARM_BAND) {
      if (centeredSince == 0) centeredSince = now;
      if (now - centeredSince >= ARM_MS) {
        armed = true;
        Serial.println("ARMADO. Gira el potenciometro: un lado adelante, otro atras.");
      }
    } else {
      centeredSince = 0;
    }
  }

  int speed = 0;
  if (armed && !estop) {
    int d = raw - potCenter;
    if (abs(d) > DEADZONE) {
      int span = 2048 - DEADZONE;
      int mag = constrain(abs(d) - DEADZONE, 0, span);
      speed = (long)mag * MAX_SPEED / span;
      if (d < 0) speed = -speed;
    }
  }

  if (now - lastFrame >= FRAME_MS) {
    lastFrame = now;
    sendHover(speed);
  }

  if (now - lastPrint >= 250) {
    lastPrint = now;
    Serial.printf("pot=%4d  speed=%4d  %s%s  placa: %.1f V %.2f A (tramas %lu)\n",
                  raw, speed, armed ? "ARMADO" : "sin armar", estop ? " PARO" : "",
                  battV, battA, (unsigned long)telemCount);
  }
}
