// Centrado de los 2 servos del cuello antes de montarlos (ESP32). Version ESP32 de servo_center (Arduino Mega).
// Deja los dos servos quietos en la mitad de su recorrido (90 grados = 1500 us)
// para poner el horn / la cuna alineados con el robot mirando al frente.
// Placa: "ESP32 Dev Module". Libreria: ESP32Servo (Gestor de librerias).
//
// Conexion (servos MG995/MG996R):
//   Servo BASE (giro)        senal naranja/amarillo -> GPIO13   (mismos pines que neck.ino)
//   Servo SUPERIOR (cabeceo) senal naranja/amarillo -> GPIO14
//   Rojo de los servos  -> +5..6 V de una fuente o buck aparte (NO el 5V/VIN del ESP32)
//   Marron/negro        -> GND de esa fuente, unido a un GND del ESP32
//   La senal de 3.3 V del ESP32 basta para estos servos alimentados a 5 V.
//
// Limites fisicos (el codigo nunca los sobrepasa): base 45..135, cuello (superior) 40..105 grados.
// Los movimientos son lentos y suaves: curva S con pico de velocidad speedDps grados/s (cambiable con "V").
//
// Serial 115200: "P 95" mueve la base, "T 85" el superior (se recortan a los limites),
// "C" vuelve los dos al centro (90), "V 20" velocidad en grados/s (5..90), "Q" imprime posicion.
#include <ESP32Servo.h>

const int PIN_BASE = 13;
const int PIN_TOP  = 14;
const int MIN_US = 500;    // pulso a 0 grados
const int MAX_US = 2500;   // pulso a 180 grados -> 90 grados = 1500 us
const int CENTER = 90;
const int BASE_MIN = 45, BASE_MAX = 135;   // limites fisicos de la base (giro)
const int TOP_MIN = 40,  TOP_MAX = 105;    // limites fisicos del cuello (cabeceo)
int speedDps = 15;                         // velocidad MAXIMA del movimiento (en mitad del recorrido), grados por segundo

// Cada eje sigue una trayectoria suave (curva S: acelera y frena sin tirones) y manda pulsos en microsegundos
// con resolucion fina. Con peso, mandar grados enteros daba un escalon de ~11 us por grado y el servo vibraba.
struct Axis {
  Servo srv;
  float cur = CENTER, start = CENTER;      // posicion actual / de salida, en grados (con decimales)
  int target = CENTER;                     // destino
  unsigned long t0 = 0;                    // cuando empezo este movimiento
  float dur = 0.0f;                        // duracion del movimiento, segundos
};
Axis base, top;
unsigned long lastStep = 0;

void setTarget(Axis &a, int t) {
  if (t == a.target) return;
  a.start = a.cur;
  a.target = t;
  a.t0 = millis();
  a.dur = max(0.2f, 1.5f * fabsf(t - a.cur) / speedDps);  // la curva S tiene su pico de velocidad a 1.5x la media
}

void update(Axis &a) {
  float u = (millis() - a.t0) / 1000.0f / (a.dur > 0 ? a.dur : 1.0f);
  if (u >= 1.0f) a.cur = a.target;
  else a.cur = a.start + (a.target - a.start) * (u * u * (3 - 2 * u));
  a.srv.writeMicroseconds(lroundf(MIN_US + a.cur / 180.0f * (MAX_US - MIN_US)));
}

void report() {
  Serial.print("POS base="); Serial.print(base.cur, 1);
  Serial.print(" superior="); Serial.print(top.cur, 1);
  Serial.print(" -> destino "); Serial.print(base.target);
  Serial.print("/"); Serial.print(top.target);
  Serial.print(" vel="); Serial.print(speedDps); Serial.println(" deg/s");
}

// Se llama desde loop() cada 20 ms (un periodo de servo), sin bloquear la lectura serie
void step() {
  unsigned long now = millis();
  if (now - lastStep < 20) return;
  lastStep = now;
  update(base);
  update(top);
}

void setup() {
  Serial.begin(115200);
  // Cada servo en su propio temporizador del ESP32 (evita interferencias entre los dos canales)
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  // attach() arranca emitiendo 1500 us (centro), sin salto a 0
  base.srv.setPeriodHertz(50);
  top.srv.setPeriodHertz(50);
  base.srv.attach(PIN_BASE, MIN_US, MAX_US);
  delay(500);              // uno y luego otro para no sumar el pico de arranque
  top.srv.attach(PIN_TOP, MIN_US, MAX_US);
  Serial.println("Servos en el centro (90). Comandos: P <deg>, T <deg>, C, V <deg/s>, Q");
  Serial.println("Limites: base 45..135, superior 40..105");
  lastStep = millis();
  report();
}

// Lee una linea completa (hasta Enter): el monitor manda tecla a tecla.
char line[24];
byte len = 0;

void handle(char *s) {
  while (*s == ' ') s++;
  char c = toupper(*s);
  if (!c) return;
  int v = atoi(s + 1);       // "P 100", "P100" y "p 100" valen
  if (c == 'P') setTarget(base, constrain(v, BASE_MIN, BASE_MAX));
  else if (c == 'T') setTarget(top, constrain(v, TOP_MIN, TOP_MAX));
  else if (c == 'C') { setTarget(base, CENTER); setTarget(top, CENTER); }
  else if (c == 'V') speedDps = constrain(v, 5, 90);
  else if (c != 'Q') { Serial.println("? usa P <deg>, T <deg>, C, V <deg/s>, Q"); return; }
  report();
}

void loop() {
  step();
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      line[len] = 0;
      if (len) handle(line);
      len = 0;
    } else if (len < sizeof(line) - 1) {
      line[len++] = ch;
    }
  }
}
