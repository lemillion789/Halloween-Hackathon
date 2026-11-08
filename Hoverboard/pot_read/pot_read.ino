// Lectura del potenciometro, sin hoverboard. Abre el monitor serie a 115200.
//
// Cableado (DevKit ESP32 de 30 pines, todo en el mismo lado):
//   3V3   -> pata 3 del potenciometro (entrada)   | si lo cambias con la 1, solo se invierte el sentido
//   GND   -> pata 1 del potenciometro (tierra)
//   GPIO4 <- pata 2 del potenciometro (cursor, el del medio)
//
// Muestra cada 100 ms: valor crudo (0..4095), voltaje, porcentaje, y el minimo y maximo vistos.
// Gira el pot de un extremo al otro para ver el rango real. Comando por serie: 'r' reinicia min/max.
//
// Placa: "ESP32 Dev Module". No necesita bibliotecas externas.

const int POT_PIN = 4;

int vmin = 4095, vmax = 0;

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  delay(300);
  Serial.println("Lectura del potenciometro en GPIO4. 'r' = reiniciar min/max.");
}

void loop() {
  if (Serial.available() && Serial.read() == 'r') { vmin = 4095; vmax = 0; }

  long s = 0;
  for (int i = 0; i < 16; i++) s += analogRead(POT_PIN);
  int raw = s / 16;
  vmin = min(vmin, raw);
  vmax = max(vmax, raw);

  Serial.printf("raw=%4d  %.2f V  %3d %%   min=%4d  max=%4d\n",
                raw, analogReadMilliVolts(POT_PIN) / 1000.0, raw * 100 / 4095, vmin, vmax);
  delay(100);
}
