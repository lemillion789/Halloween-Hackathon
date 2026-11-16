// Cuello + hoverboard + ultrasonido en un ESP32-WROOM (sustituye al Arduino Mega). Serial USB 115200.
// Librerias: ESP32Servo (Gestor de librerias). Placa: "ESP32 Dev Module".
//
// Pines (evitan los de arranque):
//   Servo giro   GPIO13      Servo cabeceo GPIO14   (alimentar servos con regulador externo, GND comun)
//   Hoverboard   DOS placas independientes (firmware Gen2.x REMOTE_UARTBUS de Hoverboard/firmware_src), cada una en su UART, 19200, 3.3 V:
//                derecha (SLAVE_ID 0): UART2 RX=GPIO16 (desde PB6 placa), TX=GPIO17 (hacia PB7 placa)
//                izquierda (SLAVE_ID 1): UART1 RX=GPIO19 (desde PB6 placa), TX=GPIO21 (hacia PB7 placa)
//                GND comun. No unir los TX de las dos placas. Mezcla en el ESP32: izq = v - giro, der = v + giro.
//                PROTECCION: si falta la telemetria de CUALQUIERA de las dos placas (> TELEM_TIMEOUT_MS) se manda 0 a las dos.
//   HC-SR04      TRIG=GPIO25, ECHO=GPIO26 (con divisor 1k/2k si el sensor saca 5 V)
//   Paro fisico  GPIO27 a GND (INPUT_PULLUP): pulsado = ruedas paradas
//   Encendido    modulo de reles (SRD-05VDC-SL-C, nivel BAJO, VCC a 5 V): IN1=GPIO32 -> placa derecha, IN2=GPIO33 -> placa izquierda.
//                Cada rele cierra (COM-NO) los 2 pines del boton de SU placa ~1 s (como pulsar). OFF = pin en alta impedancia.
//
// Comandos (una linea):
//   P <grados>   giro 45..135, detiene el barrido
//   T <grados>   cabeceo TILT_MIN..TILT_MAX
//   S            activa el barrido del giro (arranca quieto en el centro)
//   Q            responde "POS <giro> <cabeceo>"
//   H 1 / H 0    habilita/deshabilita el hoverboard (arranca DESHABILITADO: no se envia nada)
//   H L          habilita SOLO la rueda izquierda (V <vel>; la derecha recibe 0 y no se exige su telemetria)
//   R <ms>       ms por grado al mover P/T (5..200, por defecto 25 = 40 grados/s)
//   V <vel> <giro>  velocidad y giro del hoverboard (-MAX_SPEED..MAX_SPEED); expira en CMD_TIMEOUT_MS
//                   (giro > 0 = gira hacia la izquierda: la rueda derecha va mas rapida; si es al reves, invertir STEER_SIGN)
//   W            responde "HOVER R <V> <A> <v> <odom> <n> L <V> <A> <v> <odom> <n> OK|FALLO"
//   X            paro (vel 0)
//   E            enciende las dos placas del hoverboard (pulso de ~1 s en los dos reles; no actua con el paro pulsado)
//   U            responde "DIST <cm>" (-1 = sin lectura)
// Seguridad: sin comandos V durante CMD_TIMEOUT_MS -> vel 0; obstaculo < STOP_CM -> no avanza.
#include <ESP32Servo.h>

const int PAN_PIN = 13, TILT_PIN = 14;
const int RX_R = 16, TX_R = 17;            // UART2 -> placa derecha (ID 0)
const int RX_L = 19, TX_L = 21;            // UART1 remapeado -> placa izquierda (ID 1)
const int TRIG_PIN = 25, ECHO_PIN = 26;
const int ESTOP_PIN = 27;
const int RELAY_R = 32, RELAY_L = 33;       // IN1 / IN2 del modulo de reles (activos en nivel BAJO)
const unsigned long POWER_PULSE_MS = 1000;
unsigned long powerPulseUntil = 0;

const int PAN_MIN = 45, PAN_MAX = 135, PAN_CENTER = 90;
const int TILT_MIN = 40, TILT_MAX = 105, TILT_CENTER = 90;   // limites fisicos del cuello (medidos por el usuario)
const unsigned long SWEEP_MS = 20;
unsigned long gotoMs = 25;               // ms por grado al ir a P/T (25 = 40 grados/s); cambiar con `R <ms>`

const int MAX_SPEED = 150;                 // limite de software (unidades EFeru, max firmware 1000)
const unsigned long CMD_TIMEOUT_MS = 300;
const unsigned long TELEM_TIMEOUT_MS = 300;  // sin telemetria de una placa mas de esto -> parar las dos
const int SIGN_RIGHT = 1, SIGN_LEFT = 1;     // 1 con el firmware *_nobeep (placa izq. con SPEED_COEFFICIENT 1); -1 con el firmware antiguo (ruedas espejadas)
const float GAIN_RIGHT = 1.0, GAIN_LEFT = 1.0; // medido el 8 nov con 2 UART: a igual orden giran igual (R/L = 0.99); recalibrar con carga
const int STEER_SIGN = 1;                    // invertir si el giro sale al reves
const int START_SPEED = 60;                  // el firmware pone a 0 todo < 50 (STAND_STILL_THRESHOLD)
const int STOP_CM = 40;

// Telemetria de cada placa: 0xABCD (CD AB), slave, int16 v*100, uint16 V*100, int16 A*100, int32 odom, crc (15 bytes)
struct Telem { float v = -1, a = -1, speed = 0; int32_t odom = 0; uint32_t count = 0; unsigned long last = 0; };
struct Parser { uint8_t buf[15]; int pos = 0; };
Servo pan, tilt;
int panPos = PAN_CENTER, panTarget = PAN_CENTER, tiltPos = TILT_CENTER, tiltTarget = TILT_CENTER;
int dir = 1;
bool sweeping = false;                     // arranca quieto en el centro; `S` activa el barrido
unsigned long lastPan = 0, lastTilt = 0;

bool hoverOn = false;
bool leftOnly = false;                     // `H L`: solo la rueda izquierda (la derecha tiene PB6 danado, 15 nov)
int cmdSpeed = 0, cmdSteer = 0;
unsigned long lastCmd = 0, lastFrame = 0;

volatile unsigned long echoStart = 0, echoUs = 0;
volatile bool echoNew = false;
float distCm = -1;
unsigned long lastTrig = 0;

void IRAM_ATTR onEcho() {
  if (digitalRead(ECHO_PIN)) echoStart = micros();
  else { echoUs = micros() - echoStart; echoNew = true; }
}

// Trama Gen2.x "REMOTE_UARTBUS" (tipo 1) a cada placa por su propio UART
const unsigned long HOVER_BAUD = 19200;
const uint8_t ID_RIGHT = 0, ID_LEFT = 1;   // SLAVE_ID de cada placa flasheada
HardwareSerial &PORT_R = Serial2;
HardwareSerial &PORT_L = Serial1;
const uint8_t HOVER_STATE = 32;    // 32 = LEDs de bateria; 64 = deshabilitar; 128 = apagar
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

Telem telemR, telemL;
Parser parserR, parserL;
int lastSentR = 0, lastSentL = 0;   // ultimo valor enviado a cada placa (diagnostico en W)
bool hoverWasOk = false;           // para avisar una sola vez por transicion

uint16_t crc16(const uint8_t *p, int n) {   // CRC-16/XMODEM (poly 0x1021, init 0)
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

void readTelemetry(HardwareSerial &port, Parser &p, Telem &t) {
  while (port.available()) {
    uint8_t b = port.read();
    if (p.pos == 0 && b != 0xCD) continue;
    if (p.pos == 1 && b != 0xAB) { p.pos = 0; continue; }
    p.buf[p.pos++] = b;
    if (p.pos == 15) {
      p.pos = 0;
      uint16_t crcRx = p.buf[13] | (p.buf[14] << 8);
      (void)crcRx;                                  // el CRC de la telemetria no se valida; se filtra por rango
      int16_t sp = p.buf[3] | (p.buf[4] << 8);
      uint16_t v = p.buf[5] | (p.buf[6] << 8);
      int16_t a = p.buf[7] | (p.buf[8] << 8);
      int32_t odom = (int32_t)(p.buf[9] | (p.buf[10] << 8) | (p.buf[11] << 16) | ((uint32_t)p.buf[12] << 24));
      if (v < 6000) {
        t.v = v / 100.0; t.a = a / 100.0; t.speed = sp / 100.0;
        t.odom = odom; t.count++; t.last = millis();
      }
    }
  }
}

// Convierte una orden de rueda (con signo) en el valor que se envia: ganancia, sentido y salida de la zona muerta
int wheelCmd(float x, float gain, int sign) {
  int v = (int)lroundf(x * gain);
  if (v == 0) return 0;
  int mag = max(abs(v), START_SPEED);
  mag = min(mag, MAX_SPEED);
  return sign * (v > 0 ? mag : -mag);
}

void relaysOn(bool on) {                     // nivel bajo = activo; apagado = alta impedancia (no queda medio activado a 3,3 V)
  int pins[2] = {RELAY_R, RELAY_L};
  for (int i = 0; i < 2; i++) {
    if (on) { pinMode(pins[i], OUTPUT); digitalWrite(pins[i], LOW); }
    else pinMode(pins[i], INPUT);
  }
}

void updateDistance() {
  unsigned long now = millis();
  if (now - lastTrig >= 60) {
    lastTrig = now;
    digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10); digitalWrite(TRIG_PIN, LOW);
  }
  if (echoNew) {
    unsigned long us = echoUs;
    echoNew = false;
    float d = us / 58.0;
    distCm = (d > 2 && d < 400) ? d : -1;
  }
}

void handleSerial() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.startsWith("P ")) {
    panTarget = constrain(line.substring(2).toInt(), PAN_MIN, PAN_MAX);
    sweeping = false;
    Serial.print("OK P "); Serial.println(panTarget);
  } else if (line.startsWith("T ")) {
    tiltTarget = constrain(line.substring(2).toInt(), TILT_MIN, TILT_MAX);
    Serial.print("OK T "); Serial.println(tiltTarget);
  } else if (line == "S") {
    sweeping = true;
    dir = (panPos >= PAN_MAX) ? -1 : (panPos <= PAN_MIN ? 1 : dir);
    Serial.println("OK S");
  } else if (line == "Q") {
    Serial.print("POS "); Serial.print(panPos); Serial.print(' '); Serial.println(tiltPos);
  } else if (line.startsWith("H ")) {
    String arg = line.substring(2); arg.trim();
    leftOnly = (arg == "L");
    hoverOn = leftOnly || arg.toInt() != 0;
    cmdSpeed = cmdSteer = 0;
    Serial.print("OK H "); Serial.println(leftOnly ? "L (solo rueda izquierda)" : (hoverOn ? "1" : "0"));
  } else if (line.startsWith("V ")) {
    int sp = 0, st = 0;
    if (sscanf(line.c_str() + 2, "%d %d", &sp, &st) >= 1) {
      cmdSpeed = constrain(sp, -MAX_SPEED, MAX_SPEED);
      cmdSteer = constrain(st, -MAX_SPEED, MAX_SPEED);
      lastCmd = millis();
    }
  } else if (line == "X") {
    cmdSpeed = cmdSteer = 0;
    Serial.println("OK X");
  } else if (line == "E") {
    if (digitalRead(ESTOP_PIN) == LOW) {
      Serial.println("NO: paro pulsado");
    } else {
      relaysOn(true);
      powerPulseUntil = millis() + POWER_PULSE_MS;
      Serial.println("OK E (encendiendo las dos placas)");
    }
  } else if (line == "W") {
    unsigned long now = millis();
    bool ok = telemR.count && telemL.count && (long)(now - telemR.last) <= (long)TELEM_TIMEOUT_MS && (long)(now - telemL.last) <= (long)TELEM_TIMEOUT_MS;
    Serial.printf("HOVER R %.1f %.2f %.2f %ld %lu L %.1f %.2f %.2f %ld %lu %s\n",
                  telemR.v, telemR.a, telemR.speed, (long)telemR.odom, (unsigned long)telemR.count,
                  telemL.v, telemL.a, telemL.speed, (long)telemL.odom, (unsigned long)telemL.count, ok ? "OK" : "FALLO");
    Serial.printf("ESTADO hoverOn=%d cmd=%d/%d edad_cmd=%lu paro=%s dist=%d enviado R=%d L=%d\n", hoverOn, cmdSpeed, cmdSteer,
                  now - lastCmd, digitalRead(ESTOP_PIN) == LOW ? "PULSADO" : "libre", (int)distCm, lastSentR, lastSentL);
  } else if (line.startsWith("R ")) {
    gotoMs = constrain(line.substring(2).toInt(), 5, 200);
    Serial.print("OK R "); Serial.println(gotoMs);
  } else if (line == "U") {
    Serial.print("DIST "); Serial.println((int)distCm);
  }
}

void stepServos(unsigned long now) {
  if (sweeping) {
    if (now - lastPan >= SWEEP_MS) {
      lastPan = now;
      panPos += dir;
      if (panPos >= PAN_MAX) { panPos = PAN_MAX; dir = -1; }
      if (panPos <= PAN_MIN) { panPos = PAN_MIN; dir = 1; }
      pan.write(panPos);
    }
  } else if (panPos != panTarget && now - lastPan >= gotoMs) {
    lastPan = now;
    panPos += (panTarget > panPos) ? 1 : -1;
    pan.write(panPos);
  }
  if (tiltPos != tiltTarget && now - lastTilt >= gotoMs) {
    lastTilt = now;
    tiltPos += (tiltTarget > tiltPos) ? 1 : -1;
    tilt.write(tiltPos);
  }
}

void updateHover(unsigned long now) {
  if (powerPulseUntil && (long)(now - powerPulseUntil) >= 0) { relaysOn(false); powerPulseUntil = 0; }
  readTelemetry(PORT_R, parserR, telemR);                // siempre se leen (vaciar buffers)
  readTelemetry(PORT_L, parserL, telemL);
  if (!hoverOn) { hoverWasOk = false; return; }          // deshabilitado: no se manda nada, las placas se paran a los 500 ms
  int sp = cmdSpeed, st = cmdSteer;
  if (now - lastCmd > CMD_TIMEOUT_MS) sp = st = 0;       // la Jetson dejo de mandar
  if (digitalRead(ESTOP_PIN) == LOW) sp = st = 0;        // paro fisico
  if (sp > 0 && distCm > 0 && distCm < STOP_CM) sp = 0; // obstaculo adelante

  // Proteccion: las DOS placas deben responder, si no se paran las dos (evita girar de golpe con una sola rueda)
  bool leftOk = telemL.count && (long)(now - telemL.last) <= (long)TELEM_TIMEOUT_MS;
  bool rightOk = telemR.count && (long)(now - telemR.last) <= (long)TELEM_TIMEOUT_MS;
  bool boardsOk = leftOnly ? leftOk : (leftOk && rightOk);   // modo H L: basta con la izquierda
  if (!boardsOk) sp = st = 0;
  if (!boardsOk && hoverWasOk) Serial.println("FALLO hoverboard: una placa no responde, ruedas paradas");
  if (boardsOk && !hoverWasOk) Serial.println("OK hoverboard: las dos placas responden");
  hoverWasOk = boardsOk;

  if (now - lastFrame >= 25) {                           // 40 Hz; las dos tramas salen juntas, cada una por su UART
    lastFrame = now;
    int lm = leftOnly ? sp : sp - STEER_SIGN * st;          // H L: la izquierda solo avanza/retrocede, la derecha a 0
    int rm = leftOnly ? 0 : sp + STEER_SIGN * st;
    lastSentR = wheelCmd(rm, GAIN_RIGHT, SIGN_RIGHT);
    lastSentL = wheelCmd(lm, GAIN_LEFT, SIGN_LEFT);
    sendHover(PORT_R, ID_RIGHT, lastSentR);
    sendHover(PORT_L, ID_LEFT, lastSentL);
  }
}

void setup() {
  Serial.begin(115200);
  PORT_R.begin(HOVER_BAUD, SERIAL_8N1, RX_R, TX_R);
  PORT_L.begin(HOVER_BAUD, SERIAL_8N1, RX_L, TX_L);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(ESTOP_PIN, INPUT_PULLUP);
  relaysOn(false);
  attachInterrupt(digitalPinToInterrupt(ECHO_PIN), onEcho, CHANGE);
  pan.setPeriodHertz(50);  tilt.setPeriodHertz(50);
  pan.attach(PAN_PIN, 500, 2400);
  tilt.attach(TILT_PIN, 500, 2400);
  pan.write(panPos);
  tilt.write(tiltPos);
  delay(1500);
}

void loop() {
  unsigned long now = millis();
  handleSerial();
  updateDistance();
  stepServos(now);
  updateHover(now);
}
