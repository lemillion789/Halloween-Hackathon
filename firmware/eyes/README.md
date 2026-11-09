# Ojos TFT (ESP32 + 2x ST7735 1.8" 128x160)

## Cableado (ESP32 DevKit "ESP32-WROOM", 3.3 V)
Los pines SPI van en paralelo a ambas pantallas; solo CS es distinto.

| Pin TFT | ESP32 (ambas)  | Nota |
|---|---|---|
| VCC | 3V3 | NO usar 5 V |
| GND | GND | |
| SCK / CLK | GPIO18 | compartido |
| SDA / MOSI | GPIO23 | compartido |
| A0 / DC | GPIO16 | compartido |
| RESET | GPIO4 | compartido |
| LED / BL | 3V3 | retroiluminacion siempre encendida (o GPIO25 para PWM; GPIO21 ahora es SDA del IMU) |
| CS | GPIO17 (ojo izq) / GPIO5 (ojo der) | uno por pantalla |

Si tu modulo lleva pin SD/TFT_CS de tarjeta SD, dejalo sin conectar.

### IMU: modulo GY-521 (InvenSense MPU-6050), I2C
El firmware tambien acepta MPU6500/9250 (mismos registros).
| Pin IMU | ESP32 | Nota |
|---|---|---|
| VCC | 3V3 | el GY-521 trae regulador y pull-ups de 2.2k a 3.3 V; tambien acepta 5 V |
| GND | GND | |
| SDA | GPIO21 | I2C por defecto, no choca con las TFT |
| SCL | GPIO22 | |
| AD0 | sin conectar | pull-down en la placa -> 0x68 (a 3V3 = 0x69; se detectan ambas) |
| XDA / XCL / INT | sin conectar | bus auxiliar e interrupcion, no se usan |

Al arrancar calibra el giroscopio (~0.5 s): mantener la cabeza quieta. Rangos: +-4 g, +-500 grados/s.
Pitch/roll con filtro complementario. Si `SHAKE_DIZZY` = 1, sacudir la cabeza (>400 grados/s) pone mood `dizzy` 3 s.

### LEDs rojos interiores (cadena con transistor)
| Elemento | Conexion |
|---|---|
| KSP2222A (NPN, cara plana al frente: E B C) | E -> GND, B -> 1 k -> GPIO32, C -> pata corta (-) de todos los LEDs |
| cada LED rojo (3) | pata larga (+) -> su propia 100 ohm -> 3V3 |

~12 mA por LED (36 mA los 3). Para mas de ~10 LEDs usar 5V con 220 ohm por LED. Al arrancar brillo 255. Probar con `firmware/led_test/`.

Pines libres que quedan para mas cosas: 25 (reservado backlight PWM), 26, 27, 33 (E/S) y 34, 35, 36, 39 (solo entrada).

## Compilar y subir
    arduino-cli core install esp32:esp32
    arduino-cli lib install "Adafruit GFX Library" "Adafruit ST7735 and ST7789 Library"
    arduino-cli compile --fqbn esp32:esp32:esp32 firmware/eyes
    arduino-cli upload  --fqbn esp32:esp32:esp32 -p /dev/ttyUSB0 firmware/eyes

## Comandos serial (115200)
`L 0.5 -0.2` mirar | `M <mood>` | `B` parpadear | `D` demo (cambia de expresion cada 3 s)
Moods: neutral angry happy surprised sleepy sad suspicious evil dead possessed dizzy scared

LEDs: `G 255` brillo de los LEDs rojos (0..255) | `G P` latido suave | `G H [bpm]` latido de corazon pum-pum

IMU: `I` una lectura | `I 1` / `I 0` stream a 20 Hz | `I C` recalibrar giroscopio
Respuesta: `IMU <pitch> <roll> <ax> <ay> <az> <gx> <gy> <gz>` (grados, g, grados/s)

Centrado fisico de los ojos (se guarda en la flash/NVS, namespace `eyes`):
`O` -> `OFS <lx> <ly> <rx> <ry>` | `O L <dx> <dy>` / `O R <dx> <dy>` desplaza cada ojo en pixeles (+-30, sin guardar)
`O S` guardar | `O E` recargar lo guardado | `O 0` todo a 0 (sin guardar) | `C 1` / `C 0` modo calibracion (mirada fija al centro, sin parpadeo, cruz verde)
Desde el panel `tools/head_control.py`: tarjeta "Centrado de ojos" (flechas/sliders por ojo, "Guardar en ESP32").
