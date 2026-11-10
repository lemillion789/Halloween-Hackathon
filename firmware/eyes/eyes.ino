// Ojos de la calavera: 2x TFT ST7735 128x160 (verticales) en un ESP32, bus SPI compartido, CS separados.
// Comandos por serial (115200):
//   L <x> <y>   mirar, x/y en -1..1
//   M <mood>    neutral angry happy surprised sleepy sad suspicious evil dead possessed dizzy scared
//   B           parpadear
//   D           activa/desactiva modo demo (recorre todas las expresiones)
//   I           una lectura del IMU | I 1 / I 0 stream on/off (20 Hz) | I C recalibrar giroscopio
//               formato: IMU <pitch> <roll> <ax> <ay> <az> <gx> <gy> <gz>  (grados, g, grados/s)
//   G <0..255>  brillo de los LEDs rojos interiores (al arrancar: 255) | G P latido suave
//   G H [bpm]   latido de corazon "pum-pum ... pum-pum" (por defecto 70 bpm)
//   O           ver el centrado: responde OFS <lx> <ly> <rx> <ry> (pixeles)
//   O L <dx> <dy> / O R <dx> <dy>  desplaza el ojo izquierdo/derecho (+-OFS_MAX px, sin guardar)
//   O S         guarda el centrado en flash (NVS) | O 0 vuelve a 0 0 0 0 (sin guardar) | O E recarga lo guardado
//   C 1 / C 0   modo calibracion: mirada al centro, sin parpadeo, con cruz en el centro del ojo
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#include <Wire.h>
#include <math.h>
#include <Preferences.h>

// Pines (ver README.md). SCK=18, MOSI=23 son los de VSPI por defecto.
#define PIN_DC   16
#define PIN_RST  4
#define PIN_CS_L 17  // cableado fisico invertido: la pantalla del GPIO17 es el ojo izquierdo
#define PIN_CS_R 5
// IMU (MPU6050/6500/9250) por I2C en los pines por defecto del ESP32, libres respecto a las TFT.
#define PIN_SDA  21
#define PIN_SCL  22
// Cadena de 3 LEDs rojos dentro de la calavera: 3V3, 100 ohm por LED, transistor KSP2222A (base por 1 k).
// PWM, pin alto = encendido. 25 queda libre para el backlight de las TFT.
#define PIN_LEDS 32
#define LED_DEFAULT 255  // brillo al arrancar, 0..255
#define SHAKE_DIZZY 1      // 1 = sacudir la cabeza pone los ojos mareados
#define SHAKE_DPS   400.0  // umbral de giro (grados/s) para considerar sacudida

// Pantallas en vertical. 0 = pines arriba; 2 = pines abajo (girado 180).
#define ROTATION 2

Adafruit_ST7735 tftL(PIN_CS_L, PIN_DC, -1);
Adafruit_ST7735 tftR(PIN_CS_R, PIN_DC, -1);
GFXcanvas16 canvas(128, 160);  // vertical, un buffer reutilizado para ambos ojos

const int W = 128, H = 160, CX = W / 2, CY = H / 2;
const uint16_t C_BG = 0x0000;
const int R = 58;  // radio del globo ocular
const uint16_t C_PUPIL = 0x0000;

enum Mood { NEUTRAL, ANGRY, HAPPY, SURPRISED, SLEEPY, SAD, SUSPICIOUS, EVIL, DEAD, POSSESSED, DIZZY, SCARED, MOOD_COUNT };
const char *MOOD_NAMES[MOOD_COUNT] = {"neutral", "angry", "happy", "surprised", "sleepy", "sad",
                                      "suspicious", "evil", "dead", "possessed", "dizzy", "scared"};
Mood mood = ANGRY;  // por defecto enojado

float lookX = 0, lookY = 0;      // posicion actual
float tgtX = 0, tgtY = 0;        // destino
float lid = 1.0, lidTgt = 1.0;   // apertura del parpadeo: 1 abierto, 0 cerrado
uint32_t nextBlink = 0, nextSaccade = 0, blinkEnd = 0;
bool demo = false;
uint32_t nextDemo = 0;

// Centrado fisico: cada ojo se dibuja desplazado (dx, dy) pixeles en su pantalla. Se guarda en NVS.
const int OFS_MAX = 30;
// Centrado fisico calibrado el 10 nov (valores por defecto si la NVS esta vacia)
const int OFS_DEF_LX = 2, OFS_DEF_LY = -17, OFS_DEF_RX = -2, OFS_DEF_RY = -13;
int ofsLx = OFS_DEF_LX, ofsLy = OFS_DEF_LY, ofsRx = OFS_DEF_RX, ofsRy = OFS_DEF_RY;
bool ofsDirty = true;  // borrar la pantalla al cambiar el desplazamiento (quedan bordes viejos)
bool calib = false;
Preferences prefs;

void ofsLoad() {
  prefs.begin("eyes", true);
  ofsLx = prefs.getInt("lx", OFS_DEF_LX);
  ofsLy = prefs.getInt("ly", OFS_DEF_LY);
  ofsRx = prefs.getInt("rx", OFS_DEF_RX);
  ofsRy = prefs.getInt("ry", OFS_DEF_RY);
  prefs.end();
  ofsDirty = true;
}

void ofsSave() {
  prefs.begin("eyes", false);
  prefs.putInt("lx", ofsLx);
  prefs.putInt("ly", ofsLy);
  prefs.putInt("rx", ofsRx);
  prefs.putInt("ry", ofsRy);
  prefs.end();
}

void ofsPrint() { Serial.printf("OFS %d %d %d %d\n", ofsLx, ofsLy, ofsRx, ofsRy); }

// Globo ocular precalculado (degradado rosa -> rojo + venas); el ojo derecho lo usa en espejo.
// Un solo buffer: 3 de 40 KB no caben juntos en el heap contiguo del ESP32.
GFXcanvas16 sclera(128, 160);
uint32_t lcg = 1;
int rnd(int lo, int hi) {  // LCG propio: mismas venas en cada arranque
  lcg = lcg * 1664525u + 1013904223u;
  return lo + (int)((lcg >> 16) % (hi - lo + 1));
}

void buildSclera(GFXcanvas16 &c, uint32_t seed) {
  lcg = seed;
  c.fillScreen(C_BG);
  for (int rr = R; rr > 0; rr--) {
    float t = (float)rr / R;
    uint8_t red = 255 - (uint8_t)(65 * t * t * t);
    uint8_t gb = (uint8_t)(225 * (1.0 - powf(t, 2.2)));
    c.fillCircle(CX, CY, rr, tftL.color565(red, gb, gb));
  }
  uint16_t vein = tftL.color565(140, 0, 10);
  for (int i = 0; i < 18; i++) {  // venas ramificadas desde el borde hacia el iris
    float ang = rnd(0, 628) / 100.0;
    float rad = R - 3, end = rnd(24, 44);
    float px = CX + cosf(ang) * rad, py = CY + sinf(ang) * rad;
    while (rad > end) {
      rad -= rnd(5, 9);
      ang += rnd(-14, 14) / 100.0;
      float nx = CX + cosf(ang) * rad, ny = CY + sinf(ang) * rad;
      c.drawLine(px, py, nx, ny, vein);
      if (rnd(0, 2) == 0) {  // rama lateral
        float ba = ang + rnd(-6, 6) / 10.0;
        c.drawLine(nx, ny, nx + cosf(ba) * 8, ny + sinf(ba) * 8, vein);
      }
      px = nx;
      py = ny;
    }
  }
}

void drawEye(bool left) {
  uint32_t now = millis();
  if (mood == POSSESSED) {  // blanco con parpadeo
    canvas.fillScreen(C_BG);
    canvas.fillCircle(CX, CY, R, ((now / 90) % 7 == 0) ? 0xC618 : 0xFFFF);
  } else {
    uint16_t *dst = canvas.getBuffer();
    uint16_t *src = sclera.getBuffer();
    if (left) {
      memcpy(dst, src, W * H * 2);
    } else {
      for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) dst[y * W + x] = src[y * W + (W - 1 - x)];
    }
  }
  int r = R;

  // el iris se desplaza segun la mirada; el ojo izquierdo/derecho converge un poco
  int ix = CX + (int)(lookX * 20) + (left ? 3 : -3);
  int iy = CY + (int)(lookY * 28);
  if (mood == SCARED) {  // temblor
    ix += random(-3, 4);
    iy += random(-3, 4);
  }

  if (mood == DEAD) {  // X roja
    for (int d = -3; d <= 3; d++) {
      canvas.drawLine(CX - 36 + d, CY - 36, CX + 36 + d, CY + 36, 0x8000);
      canvas.drawLine(CX + 36 + d, CY - 36, CX - 36 + d, CY + 36, 0x8000);
    }
  } else if (mood == POSSESSED) {  // sin iris, solo un punto diminuto
    canvas.fillCircle(ix, iy, 3, 0x7BEF);
  } else {
    int ir = 27;
    if (mood == SURPRISED) ir = 24;
    if (mood == SCARED) ir = 22;
    if (mood == EVIL) ir = 29;
    canvas.fillCircle(ix, iy, ir, 0x6000);       // aro oscuro
    canvas.fillCircle(ix, iy, ir - 3, 0xD8A0);   // iris rojo-naranja
    canvas.fillCircle(ix, iy, ir - 6, 0xA000);

    if (mood == EVIL) {  // pupila de reptil
      canvas.fillRoundRect(ix - 5, iy - ir + 3, 10, 2 * ir - 6, 5, C_PUPIL);
    } else if (mood == DIZZY) {  // espiral giratoria
      float a0 = now / 120.0;
      for (float t = 0; t < 12.5; t += 0.15) {
        float rad = t * ir / 12.5;
        canvas.fillCircle(ix + (int)(cosf(t + a0) * rad), iy + (int)(sinf(t + a0) * rad), 2, C_PUPIL);
      }
    } else {
      int pr = 15;
      if (mood == SURPRISED) pr = 8;
      if (mood == ANGRY) pr = 11;
      if (mood == SCARED) pr = 6;
      if (mood == SAD) pr = 17;
      canvas.fillCircle(ix, iy, pr, C_PUPIL);
      if (pr >= 11) {  // aro rojo dentro de la pupila
        canvas.fillCircle(ix, iy, pr - 4, 0xC000);
        canvas.fillCircle(ix, iy, pr - 8 > 2 ? pr - 8 : 2, C_PUPIL);
      }
      canvas.fillCircle(ix - 8, iy - 9, 4, 0xFFFF);  // brillo
      canvas.fillCircle(ix + 6, iy + 8, 2, 0xFDB6);
    }
  }

  // parpados: tapar con el color de fondo
  float open = lid;
  if (mood == SLEEPY) open *= 0.45;
  if (mood == SUSPICIOUS) open *= 0.5;
  if (mood == DEAD || mood == POSSESSED) open = 1.0;
  int top = CY - r - 2 + (int)((1.0 - open) * (r + 2));
  canvas.fillRect(0, 0, W, top, C_BG);
  int bot = CY + r + 2 - (int)((1.0 - open) * (r + 2));
  canvas.fillRect(0, bot, W, H - bot, C_BG);

  int inner = left ? W : 0, outer = left ? 0 : W;
  if (mood == ANGRY) {  // inclinado hacia el centro (borde interno mas bajo)
    canvas.fillTriangle(outer, 0, inner, 0, inner, CY - 4, C_BG);
  } else if (mood == EVIL) {  // ceño aun mas marcado
    canvas.fillTriangle(outer, 0, inner, 0, inner, CY + 14, C_BG);
  } else if (mood == SAD) {  // borde externo mas bajo
    canvas.fillTriangle(outer, 0, inner, 0, outer, CY - 2, C_BG);
  } else if (mood == SUSPICIOUS) {  // un parpado superior ligeramente inclinado
    canvas.fillTriangle(outer, 0, inner, 0, inner, CY - 30, C_BG);
  } else if (mood == HAPPY) {  // parpado inferior curvo hacia arriba
    canvas.fillCircle(CX, CY + r + 22, r + 6, C_BG);
  }

  if (calib) {  // cruz en el centro del ojo para alinearlo con la cuenca
    canvas.drawFastHLine(0, CY, W, 0x07E0);
    canvas.drawFastVLine(CX, 0, H, 0x07E0);
    canvas.drawCircle(CX, CY, R, 0x07E0);
  }
}

void render() {
  if (ofsDirty) {
    tftL.fillScreen(C_BG);
    tftR.fillScreen(C_BG);
    ofsDirty = false;
  }
  drawEye(true);
  tftL.drawRGBBitmap(ofsLx, ofsLy, canvas.getBuffer(), W, H);  // la libreria recorta lo que sale de la pantalla
  drawEye(false);
  tftR.drawRGBBitmap(ofsRx, ofsRy, canvas.getBuffer(), W, H);
}

// ---- IMU: registros comunes de la familia MPU6050/6500/9250, sin librerias ----
uint8_t imuAddr = 0;             // 0 = no encontrado
float ax, ay, az, gx, gy, gz;    // g y grados/s
float gbx = 0, gby = 0, gbz = 0; // bias del giroscopio
float pitch = 0, roll = 0;       // filtro complementario, grados
bool imuStream = false;
uint32_t lastImu = 0, nextImuOut = 0, dizzyEnd = 0;
Mood moodBeforeDizzy = NEUTRAL;

void imuWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(imuAddr);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

bool imuReadRaw() {
  Wire.beginTransmission(imuAddr);
  Wire.write(0x3B);  // ACCEL_XOUT_H; 14 bytes: accel, temp, gyro
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(imuAddr, (uint8_t)14) != 14) return false;
  int16_t v[7];
  for (int i = 0; i < 7; i++) {
    uint8_t hi = Wire.read();  // dos sentencias: el orden de evaluacion de a|b no esta garantizado
    v[i] = (int16_t)((hi << 8) | Wire.read());
  }
  ax = v[0] / 8192.0;  // +-4 g
  ay = v[1] / 8192.0;
  az = v[2] / 8192.0;
  gx = v[4] / 65.5 - gbx;  // +-500 grados/s
  gy = v[5] / 65.5 - gby;
  gz = v[6] / 65.5 - gbz;
  return true;
}

void imuCalibrate() {  // la cabeza debe estar quieta ~0.5 s
  gbx = gby = gbz = 0;
  float sx = 0, sy = 0, sz = 0;
  int n = 0;
  for (int i = 0; i < 200; i++) {
    if (imuReadRaw()) {
      sx += gx;
      sy += gy;
      sz += gz;
      n++;
    }
    delay(2);
  }
  if (n) {
    gbx = sx / n;
    gby = sy / n;
    gbz = sz / n;
  }
  imuReadRaw();
  pitch = atan2f(-ax, sqrtf(ay * ay + az * az)) * RAD_TO_DEG;
  roll = atan2f(ay, az) * RAD_TO_DEG;
  lastImu = micros();
}

void imuBegin() {
  Wire.begin(PIN_SDA, PIN_SCL, 400000);
  for (uint8_t a = 0x68; a <= 0x69 && !imuAddr; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) imuAddr = a;
  }
  if (!imuAddr) {
    Serial.println("IMU no encontrado (revisar SDA=21 SCL=22, 3V3, GND)");
    return;
  }
  Wire.beginTransmission(imuAddr);
  Wire.write(0x75);  // WHO_AM_I: 0x68 MPU6050, 0x70 MPU6500, 0x71/0x73 MPU9250/9255
  Wire.endTransmission(false);
  Wire.requestFrom(imuAddr, (uint8_t)1);
  uint8_t who = Wire.read();
  imuWrite(0x6B, 0x80);  // reset
  delay(100);
  imuWrite(0x6B, 0x01);  // despertar, reloj del PLL del giro
  imuWrite(0x1A, 0x03);  // filtro paso bajo ~44 Hz
  imuWrite(0x1B, 0x08);  // giro +-500 grados/s
  imuWrite(0x1C, 0x08);  // accel +-4 g
  delay(50);
  Serial.printf("IMU en 0x%02X, WHO_AM_I=0x%02X\n", imuAddr, who);
  imuCalibrate();
}

void imuPrint() {
  Serial.printf("IMU %.1f %.1f %.3f %.3f %.3f %.1f %.1f %.1f\n", pitch, roll, ax, ay, az, gx, gy, gz);
}

void imuUpdate() {
  if (!imuAddr || !imuReadRaw()) return;
  uint32_t t = micros();
  float dt = (t - lastImu) / 1e6;
  lastImu = t;
  if (dt > 0.2) dt = 0.2;  // tras una pausa larga no integrar de mas
  float accPitch = atan2f(-ax, sqrtf(ay * ay + az * az)) * RAD_TO_DEG;
  float accRoll = atan2f(ay, az) * RAD_TO_DEG;
  pitch = 0.96 * (pitch + gy * dt) + 0.04 * accPitch;
  roll = 0.96 * (roll + gx * dt) + 0.04 * accRoll;

  uint32_t now = millis();
#if SHAKE_DIZZY
  if (!calib && sqrtf(gx * gx + gy * gy + gz * gz) > SHAKE_DPS) {
    if (now > dizzyEnd) moodBeforeDizzy = mood;
    mood = DIZZY;
    dizzyEnd = now + 3000;
  } else if (dizzyEnd && now > dizzyEnd) {
    mood = moodBeforeDizzy;
    dizzyEnd = 0;
  }
#endif
  if (imuStream && now > nextImuOut) {
    imuPrint();
    nextImuOut = now + 50;
  }
}

// ---- LEDs rojos interiores: PWM por LEDC, 5 kHz, 8 bits ----
// Los efectos corren en su propia tarea cada 10 ms: el loop tarda ~50 ms por cuadro y el latido se veria a saltos.
enum LedMode { LED_FIXED, LED_PULSE, LED_HEART };
volatile LedMode ledMode = LED_HEART;  // por defecto latido de corazon
volatile int ledBpm = 70;
volatile uint32_t heartStart = 0;

void ledBegin() {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(PIN_LEDS, 5000, 8);
#else
  ledcSetup(0, 5000, 8);
  ledcAttachPin(PIN_LEDS, 0);
#endif
}

void ledLevel(int v) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_LEDS, constrain(v, 0, 255));
#else
  ledcWrite(0, constrain(v, 0, 255));
#endif
}

// destello: sube en 30 ms y se apaga exponencialmente
float flash(int32_t dt, float amp) {
  if (dt < 0) return 0;
  if (dt < 30) return amp * dt / 30.0;
  return amp * expf(-(dt - 30) / 70.0);
}

void ledTask(void *) {
  while (true) {
    uint32_t now = millis();
    if (ledMode == LED_PULSE) {
      ledLevel(10 + (int)((sinf(now / 600.0) + 1) / 2 * 245));  // latido lento
    } else if (ledMode == LED_HEART) {  // "pum" fuerte, "pum" suave 200 ms despues, silencio
      int32_t t = (now - heartStart) % (60000 / ledBpm);
      float a = flash(t, 1.0) + flash(t - 200, 0.7);
      ledLevel(6 + (int)(249 * (a > 1 ? 1 : a)));
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void setMood(const String &m) {
  mood = NEUTRAL;
  for (int i = 0; i < MOOD_COUNT; i++)
    if (m == MOOD_NAMES[i]) mood = (Mood)i;
}

void handleSerial() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.startsWith("L ")) {
    sscanf(line.c_str() + 2, "%f %f", &tgtX, &tgtY);
    tgtX = constrain(tgtX, -1, 1);
    tgtY = constrain(tgtY, -1, 1);
    nextSaccade = millis() + 4000;  // pausa el movimiento aleatorio
  } else if (line.startsWith("M ")) {
    demo = false;
    dizzyEnd = 0;  // una orden explicita gana al mareo por sacudida
    setMood(line.substring(2));
  } else if (line == "G P") {
    ledMode = LED_PULSE;
  } else if (line.startsWith("G H")) {
    if (line.length() > 4) ledBpm = constrain(line.substring(4).toInt(), 30, 180);
    heartStart = millis();
    ledMode = LED_HEART;
  } else if (line.startsWith("G ")) {
    ledMode = LED_FIXED;
    ledLevel(line.substring(2).toInt());
  } else if (line == "I") {
    imuPrint();
  } else if (line == "I 1" || line == "I 0") {
    imuStream = (line == "I 1");
  } else if (line == "I C") {
    imuCalibrate();
    Serial.println("IMU calibrado");
  } else if (line == "O") {
    ofsPrint();
  } else if (line.startsWith("O L ") || line.startsWith("O R ")) {
    int dx = 0, dy = 0;
    sscanf(line.c_str() + 4, "%d %d", &dx, &dy);
    dx = constrain(dx, -OFS_MAX, OFS_MAX);
    dy = constrain(dy, -OFS_MAX, OFS_MAX);
    if (line[2] == 'L') {
      ofsLx = dx;
      ofsLy = dy;
    } else {
      ofsRx = dx;
      ofsRy = dy;
    }
    ofsDirty = true;
    ofsPrint();
  } else if (line == "O S") {
    ofsSave();
    Serial.print("Guardado ");
    ofsPrint();
  } else if (line == "O 0") {
    ofsLx = ofsLy = ofsRx = ofsRy = 0;
    ofsDirty = true;
    ofsPrint();
  } else if (line == "O E") {
    ofsLoad();
    ofsPrint();
  } else if (line == "C 1" || line == "C 0") {
    calib = (line == "C 1");
    if (calib) {
      demo = false;
      dizzyEnd = 0;
      mood = NEUTRAL;
    }
  } else if (line == "B") {
    blinkEnd = millis() + 150;
  } else if (line == "D") {
    demo = !demo;
    nextDemo = 0;
  }
}

void setup() {
  Serial.begin(115200);
  ledBegin();
  ledLevel(LED_DEFAULT);
  xTaskCreatePinnedToCore(ledTask, "leds", 2048, nullptr, 1, nullptr, 0);
  pinMode(PIN_RST, OUTPUT);
  digitalWrite(PIN_RST, LOW);
  delay(20);
  digitalWrite(PIN_RST, HIGH);
  delay(120);
  SPI.begin(18, -1, 23, -1);
  tftL.initR(INITR_BLACKTAB);
  tftR.initR(INITR_BLACKTAB);
  tftL.setRotation(ROTATION);
  tftR.setRotation(ROTATION);
  tftL.fillScreen(C_BG);
  tftR.fillScreen(C_BG);
  randomSeed(esp_random());
  if (!canvas.getBuffer() || !sclera.getBuffer()) {
    Serial.println("ERROR: sin memoria para los buffers");
    while (true) delay(1000);
  }
  buildSclera(sclera, 7);
  ofsLoad();
  ofsPrint();
  imuBegin();
}

void loop() {
  uint32_t now = millis();
  handleSerial();
  imuUpdate();

  if (demo && now > nextDemo) {
    mood = (Mood)((mood + 1) % MOOD_COUNT);
    Serial.println(MOOD_NAMES[mood]);
    nextDemo = now + 3000;
  }
  if (calib) {  // quieto y mirando al frente mientras se centra
    tgtX = tgtY = 0;
    nextSaccade = now + 1000;
    nextBlink = now + 1000;
  }
  if (now > nextSaccade) {  // mirada aleatoria cuando nadie la controla
    tgtX = random(-100, 101) / 100.0;
    tgtY = random(-60, 61) / 100.0;
    nextSaccade = now + random(800, 3000);
  }
  if (now > nextBlink) {
    blinkEnd = now + 150;
    nextBlink = now + random(2000, 6000);
  }
  lidTgt = (now < blinkEnd) ? 0.0 : 1.0;
  lid += (lidTgt - lid) * 0.6;
  lookX += (tgtX - lookX) * 0.35;
  lookY += (tgtY - lookY) * 0.35;

  render();
}
