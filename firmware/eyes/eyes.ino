// Ojos de la calavera: 2x TFT ST7735 128x160 (verticales) en un ESP32, bus SPI compartido, CS separados.
// Comandos por serial (115200):
//   L <x> <y>   mirar, x/y en -1..1
//   M <mood>    neutral angry happy surprised sleepy sad suspicious evil dead possessed dizzy scared
//   B           parpadear
//   D           activa/desactiva modo demo (recorre todas las expresiones)
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#include <math.h>

// Pines (ver README.md). SCK=18, MOSI=23 son los de VSPI por defecto.
#define PIN_DC   16
#define PIN_RST  4
#define PIN_CS_L 5
#define PIN_CS_R 17

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
Mood mood = NEUTRAL;

float lookX = 0, lookY = 0;      // posicion actual
float tgtX = 0, tgtY = 0;        // destino
float lid = 1.0, lidTgt = 1.0;   // apertura del parpadeo: 1 abierto, 0 cerrado
uint32_t nextBlink = 0, nextSaccade = 0, blinkEnd = 0;
bool demo = false;
uint32_t nextDemo = 0;

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
}

void render() {
  drawEye(true);
  tftL.drawRGBBitmap(0, 0, canvas.getBuffer(), W, H);
  drawEye(false);
  tftR.drawRGBBitmap(0, 0, canvas.getBuffer(), W, H);
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
    setMood(line.substring(2));
  } else if (line == "B") {
    blinkEnd = millis() + 150;
  } else if (line == "D") {
    demo = !demo;
    nextDemo = 0;
  }
}

void setup() {
  Serial.begin(115200);
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
}

void loop() {
  uint32_t now = millis();
  handleSerial();

  if (demo && now > nextDemo) {
    mood = (Mood)((mood + 1) % MOOD_COUNT);
    Serial.println(MOOD_NAMES[mood]);
    nextDemo = now + 3000;
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
