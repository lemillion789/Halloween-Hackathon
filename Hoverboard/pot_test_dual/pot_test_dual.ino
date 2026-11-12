// Prueba de bancada con LAS DOS placas a la vez, CADA UNA EN SU PROPIO UART:
// potenciometro -> ESP32 -> placas del hoverboard (firmware Gen2.x REMOTE_UARTBUS: derecha SLAVE_ID 0, izquierda SLAVE_ID 1).
// Misma velocidad (con signo y ganancia por rueda). Telemetria de las dos placas a la vez.
// SOLO con las ruedas en el aire, fuente limitada y manos lejos.
//
// Cableado (todo 3.3 V). TODO en el MISMO lado del DevKit de 30 pines (3V3, GND, 15, 2, 4, 16, 17, 5, 18, 19, 21...):
//   3V3  -> potenciometro 10k, extremo 1
//   GND  -> potenciometro 10k, extremo 2, y GND de las DOS placas del hoverboard (comun a todo)
//   GPIO4  <- cursor (el del medio) del potenciometro
//   PLACA DERECHA  (ID 0, UART2): GPIO16 (RX2) <- PB6 (TX) de la placa ; GPIO17 (TX2) -> PB7 (RX) de la placa
//   PLACA IZQUIERDA(ID 1, UART1): GPIO19 (RX1) <- PB6 (TX) de la placa ; GPIO21 (TX1) -> PB7 (RX) de la placa
//   Paro (opcional): GPIO18 a GND = parada inmediata (con pull-up interna; sin cable no hace nada)
//   No usar GPIO2, 12 y 15 (pines de arranque del ESP32).
//
// Uso: abre el monitor serie a 115200. Al arrancar hay que dejar el potenciometro en el CENTRO ~1 s
// para "armar"; mientras no este armado no se manda movimiento. Girar a un lado = adelante, al otro = atras.
// Centro = parado. Para detener: pot al centro, boton de paro, o desenchufar el ESP32 (la placa
// deshabilita el motor a los 500 ms sin tramas).
// Si una rueda gira al reves que la otra: SIGN_RIGHT / SIGN_LEFT. Si una gira de mas: GAIN_RIGHT / GAIN_LEFT.
//
// Placa: "ESP32 Dev Module". No necesita bibliotecas externas.

const int POT_PIN = 4;                     // ADC2_CH0; vale porque no usamos WiFi
const int ESTOP_PIN = 18;
const int RX_R = 16, TX_R = 17;            // UART2 -> placa derecha
const int RX_L = 19, TX_L = 21;            // UART1 (remapeado) -> placa izquierda

HardwareSerial &PORT_R = Serial2;
HardwareSerial &PORT_L = Serial1;

const unsigned long HOVER_BAUD = 19200;
const uint8_t ID_RIGHT = 0, ID_LEFT = 1;     // SLAVE_ID de cada placa
const int SIGN_RIGHT = 1, SIGN_LEFT = 1;    // +1 o -1: invierte el sentido de esa rueda. 1 con el firmware *_nobeep (placa izq. con SPEED_COEFFICIENT 1); -1 con el firmware antiguo (ruedas espejadas)
const uint8_t HOVER_STATE = 32;           // 32 = LEDs de bateria (igual que firmware/neck/neck.ino)

const int MAX_SPEED = 150;                 // 150 de 1000 = 15 % PWM maximo (limite de software)
const float GAIN_RIGHT = 1.0, GAIN_LEFT = 1.0;  // medido el 8 nov con las 2 UART, ruedas en el aire, speed=-150: a igual orden las dos giran igual (R/L = 0.99); la diferencia de 0.93 de antes ya no aparece
const int START_SPEED = 60;                // el firmware pone a 0 todo por debajo de 50 (STAND_STILL_THRESHOLD): empezar en 60 al salir de la zona muerta
const int DEADZONE = 250;                  // de 4095: ancho del "centro = parado"
const int ARM_BAND = 300;                  // el pot debe estar a +-300 del centro para armar
const unsigned long ARM_MS = 1000;
const unsigned long FRAME_MS = 25;         // 40 Hz

struct __attribute__((packed)) HoverCmd {
  uint8_t  start = '/';
  uint8_t  dataType = 1;
  uint8_t  slave = 0;
  int16_t  speed = 0;
  int16_t  steer = 0;
  uint8_t  state = HOVER_STATE;
  uint8_t  stateSlave = HOVER_STATE;
  uint16_t crc = 0;
};

// Tipos de la telemetria (antes de las funciones: el preprocesador de Arduino genera prototipos arriba)
struct Telem { float v = -1, a = -1, speed = 0; int32_t odom = 0; uint32_t count = 0; };
struct Parser { uint8_t buf[15]; int pos = 0; };

uint16_t crc16(const uint8_t *p, int n) {  // CRC-16/XMODEM (poly 0x1021, init 0), igual que neck.ino
  uint16_t crc = 0;
  while (n--) {
    crc ^= (uint16_t)*p++ << 8;
    for (int i = 0; i < 8; i++) crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : (crc << 1);
  }
  return crc;
}

void sendHover(HardwareSerial &port, uint8_t id, int speed) {
  HoverCmd c;
  c.slave = id;
  c.speed = speed;
  c.steer = 0;
  c.crc = crc16((uint8_t *)&c, sizeof(c) - 2);
  port.write((uint8_t *)&c, sizeof(c));
}

// Telemetria de cada placa: 0xABCD (CD AB), slave, int16 velocidad*100, uint16 V*100, int16 A*100, int32 odom, crc

void readTelemetry(HardwareSerial &port, Parser &p, Telem &t) {
  while (port.available()) {
    uint8_t b = port.read();
    if (p.pos == 0 && b != 0xCD) continue;
    if (p.pos == 1 && b != 0xAB) { p.pos = 0; continue; }
    p.buf[p.pos++] = b;
    if (p.pos == 15) {
      p.pos = 0;
      int16_t sp = p.buf[3] | (p.buf[4] << 8);
      uint16_t v = p.buf[5] | (p.buf[6] << 8);
      int16_t a = p.buf[7] | (p.buf[8] << 8);
      int32_t odom = (int32_t)(p.buf[9] | (p.buf[10] << 8) | (p.buf[11] << 16) | ((uint32_t)p.buf[12] << 24));
      if (v < 6000) {
        t.v = v / 100.0; t.a = a / 100.0; t.speed = sp / 100.0;
        t.odom = odom; t.count++;
      }
    }
  }
}

int readPot() {                            // media de 16 lecturas, 0..4095
  long s = 0;
  for (int i = 0; i < 16; i++) s += analogRead(POT_PIN);
  return s / 16;
}

Telem telemR, telemL;
Parser parserR, parserL;
bool armed = false;
unsigned long centeredSince = 0, lastFrame = 0, lastPrint = 0;
int potCenter = 2048;

void setup() {
  Serial.begin(115200);
  PORT_R.begin(HOVER_BAUD, SERIAL_8N1, RX_R, TX_R);
  PORT_L.begin(HOVER_BAUD, SERIAL_8N1, RX_L, TX_L);
  pinMode(ESTOP_PIN, INPUT_PULLUP);
  analogReadResolution(12);
  delay(500);
  Serial.println("Deja el potenciometro en el CENTRO para armar...");
}

void loop() {
  unsigned long now = millis();
  readTelemetry(PORT_R, parserR, telemR);
  readTelemetry(PORT_L, parserL, telemL);
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
      speed = START_SPEED + (long)mag * (MAX_SPEED - START_SPEED) / span;
      if (d < 0) speed = -speed;
    }
  }

  int cmdR = SIGN_RIGHT * (int)lroundf(GAIN_RIGHT * speed);
  int cmdL = SIGN_LEFT * (int)lroundf(GAIN_LEFT * speed);

  // Cada placa tiene su UART: las dos tramas salen a la vez, a 40 Hz
  if (now - lastFrame >= FRAME_MS) {
    lastFrame = now;
    sendHover(PORT_R, ID_RIGHT, cmdR);
    sendHover(PORT_L, ID_LEFT, cmdL);
  }

  if (now - lastPrint >= 250) {
    lastPrint = now;
    Serial.printf("pot=%4d speed=%4d (R=%4d L=%4d) %s%s | R: %.1fV %.2fA v=%.2f odom=%ld n=%lu | L: %.1fV %.2fA v=%.2f odom=%ld n=%lu\n",
                  raw, speed, cmdR, cmdL,
                  armed ? "ARMADO" : "sin armar", estop ? " PARO" : "",
                  telemR.v, telemR.a, telemR.speed, (long)telemR.odom, (unsigned long)telemR.count,
                  telemL.v, telemL.a, telemL.speed, (long)telemL.odom, (unsigned long)telemL.count);
  }
}
