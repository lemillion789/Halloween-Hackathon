// Prueba de los reles (modulo de 4 reles SRD-05VDC-SL-C) SIN el hoverboard conectado.
// Cableado: modulo VCC -> pin 5V/VIN del DevKit (5 V del USB), GND -> GND,
//           IN1 -> GPIO32 (placa derecha), IN2 -> GPIO33 (placa izquierda). Los contactos NO se conectan a nada todavia.
// Serie 115200: '1' pulso de 1 s al rele 1, '2' al rele 2, 'b' los dos a la vez,
//               'm' cambia el modo (nivel bajo / nivel alto). Cada rele debe hacer "clic" al empezar y otro al acabar.
// Modo nivel bajo (lo habitual): ON = pin a LOW; OFF = pin en alta impedancia (INPUT), asi con 3,3 V no queda medio activado.
// Placa: "ESP32 Dev Module".
const int PINS[2] = {32, 33};
bool activeLow = true;

void relay(int i, bool on) {
  if (activeLow) {
    if (on) { pinMode(PINS[i], OUTPUT); digitalWrite(PINS[i], LOW); }
    else pinMode(PINS[i], INPUT);
  } else {
    pinMode(PINS[i], OUTPUT);
    digitalWrite(PINS[i], on ? HIGH : LOW);
  }
}
void allOff() { relay(0, false); relay(1, false); }

void pulse(bool r1, bool r2) {
  if (r1) relay(0, true);
  if (r2) relay(1, true);
  delay(1000);
  allOff();
  Serial.println("pulso hecho");
}

void setup() {
  Serial.begin(115200);
  allOff();
  Serial.println("'1','2','b' = pulso de 1 s; 'm' = cambiar modo. Modo actual: nivel BAJO");
}

void loop() {
  if (!Serial.available()) return;
  char c = Serial.read();
  if (c == '1') pulse(true, false);
  else if (c == '2') pulse(false, true);
  else if (c == 'b') pulse(true, true);
  else if (c == 'm') {
    allOff();
    activeLow = !activeLow;
    allOff();
    Serial.println(activeLow ? "Modo: nivel BAJO" : "Modo: nivel ALTO");
  }
}
