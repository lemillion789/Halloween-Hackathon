// Centrado de los 2 servos del cuello antes de montarlos (Arduino Mega).
// Deja los dos servos quietos en la mitad de su recorrido (90 grados = 1500 us)
// para poner el horn / la cuna alineados con el robot mirando al frente.
//
// Conexion (servos MG995/MG996R):
//   Servo BASE (giro)        senal naranja/amarillo -> D9
//   Servo SUPERIOR (cabeceo) senal naranja/amarillo -> D10
//   Rojo de los servos  -> +5..6 V de una fuente o buck aparte (NO el 5V del Mega)
//   Marron/negro        -> GND de esa fuente, unido a un GND del Mega
//
// Serial 115200 (opcional, para afinar): "P 95" mueve la base, "T 85" el superior,
// "C" vuelve los dos al centro, "Q" imprime la posicion actual.
#include <Servo.h>

const int PIN_BASE = 9;
const int PIN_TOP  = 10;
const int MIN_US = 500;    // pulso a 0 grados
const int MAX_US = 2500;   // pulso a 180 grados -> 90 grados = 1500 us
const int CENTER = 90;

Servo base, top;
int angBase = CENTER, angTop = CENTER;

void apply() {
  base.write(angBase);
  top.write(angTop);
  Serial.print("POS base="); Serial.print(angBase);
  Serial.print(" superior="); Serial.println(angTop);
}

void setup() {
  Serial.begin(115200);
  // write() antes de attach(): el primer pulso ya es el centro (sin salto a 0)
  base.write(CENTER);
  top.write(CENTER);
  base.attach(PIN_BASE, MIN_US, MAX_US);
  delay(500);              // uno y luego otro para no sumar el pico de arranque
  top.attach(PIN_TOP, MIN_US, MAX_US);
  Serial.println("Servos en el centro (90). Comandos: P <deg>, T <deg>, C, Q");
  apply();
}

// Lee una linea completa (hasta Enter): el monitor manda tecla a tecla y
// parseInt() se rendia a 1 s devolviendo 0.
char line[24];
byte len = 0;

void handle(char *s) {
  while (*s == ' ') s++;
  char c = toupper(*s);
  if (!c) return;
  int v = atoi(s + 1);       // "P 100", "P100" y "p 100" valen
  if (c == 'P') angBase = constrain(v, 0, 180);
  else if (c == 'T') angTop = constrain(v, 0, 180);
  else if (c == 'C') { angBase = CENTER; angTop = CENTER; }
  else if (c != 'Q') { Serial.println("? usa P <deg>, T <deg>, C, Q"); return; }
  apply();
}

void loop() {
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
