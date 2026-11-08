// Prueba del servo MG996R del giro (Arduino Mega).
// Amarillo -> D9, rojo -> 5V, negro -> GND. Barrido lento entre 45 y 135 grados.
#include <Servo.h>

const int SERVO_PIN = 9;
const int MIN_ANG = 45;
const int MAX_ANG = 135;

Servo s;

void setup() {
  s.attach(SERVO_PIN);
  s.write(90);            // centro
  delay(1500);
}

void loop() {
  for (int a = 90; a <= MAX_ANG; a++) { s.write(a); delay(20); }
  for (int a = MAX_ANG; a >= MIN_ANG; a--) { s.write(a); delay(20); }
  for (int a = MIN_ANG; a <= 90; a++) { s.write(a); delay(20); }
  delay(1000);
}
