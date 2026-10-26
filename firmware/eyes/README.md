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
| LED / BL | 3V3 | retroiluminacion siempre encendida (o GPIO21 para PWM) |
| CS | GPIO5 (ojo izq) / GPIO17 (ojo der) | uno por pantalla |

Si tu modulo lleva pin SD/TFT_CS de tarjeta SD, dejalo sin conectar.

## Compilar y subir
    arduino-cli core install esp32:esp32
    arduino-cli lib install "Adafruit GFX Library" "Adafruit ST7735 and ST7789 Library"
    arduino-cli compile --fqbn esp32:esp32:esp32 firmware/eyes
    arduino-cli upload  --fqbn esp32:esp32:esp32 -p /dev/ttyUSB0 firmware/eyes

## Comandos serial (115200)
`L 0.5 -0.2` mirar | `M <mood>` | `B` parpadear | `D` demo (cambia de expresion cada 3 s)
Moods: neutral angry happy surprised sleepy sad suspicious evil dead possessed dizzy scared
