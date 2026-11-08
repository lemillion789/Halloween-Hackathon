"""Genera power_diagram.svg y neck_signals.svg (SVG a mano, con simbolos de componentes).
Uso: python3 draw.py   (sin dependencias)"""

import html
RED, BLK, ORG, GRN, BLU, YEL, GRY = "#d32f2f", "#222", "#ef6c00", "#2e7d32", "#1565c0", "#f9a825", "#666"


class SVG:
    def __init__(s, w, h):
        s.w, s.h, s.o = w, h, []

    def add(s, x): s.o.append(x)

    def line(s, pts, c=BLK, w=3, dash=None):
        p = " ".join(f"{x},{y}" for x, y in pts)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        s.add(f'<polyline points="{p}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"{d}/>')

    def dot(s, x, y, c=BLK): s.add(f'<circle cx="{x}" cy="{y}" r="5" fill="{c}"/>')

    def text(s, x, y, t, size=14, anchor="middle", c="#222", bold=False):
        for i, ln in enumerate(html.escape(str(t)).split("\n")):
            fw = ' font-weight="bold"' if bold else ""
            s.add(f'<text x="{x}" y="{y + i * (size + 3)}" font-size="{size}" text-anchor="{anchor}" fill="{c}"'
                  f' font-family="Helvetica,Arial,sans-serif"{fw}>{ln}</text>')

    def box(s, x, y, w, h, title, sub="", fill="#fff8e1", stroke="#8d6e00"):
        s.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>')
        s.text(x + w / 2, y + 24, title, 15, bold=True)
        if sub: s.text(x + w / 2, y + 44, sub, 12, c=GRY)

    def gnd(s, x, y, c=BLK):
        s.line([(x, y), (x, y + 10)], c); s.line([(x - 14, y + 10), (x + 14, y + 10)], c)
        s.line([(x - 9, y + 16), (x + 9, y + 16)], c); s.line([(x - 4, y + 22), (x + 4, y + 22)], c)

    # --- componentes verticales (x,y = punto superior, largo 60) ---
    def fuse_v(s, x, y, label):
        s.line([(x, y), (x, y + 14)]); s.add(f'<rect x="{x-9}" y="{y+14}" width="18" height="34" fill="#fff" stroke="{BLK}" stroke-width="3"/>')
        s.line([(x, y + 14), (x, y + 48)], "#999", 2); s.line([(x, y + 48), (x, y + 62)])
        s.text(x + 18, y + 36, label, 13, "start")

    def fuse_h(s, x, y, label):
        s.line([(x, y), (x + 14, y)]); s.add(f'<rect x="{x+14}" y="{y-9}" width="34" height="18" fill="#fff" stroke="{BLK}" stroke-width="3"/>')
        s.line([(x + 14, y), (x + 48, y)], "#999", 2); s.line([(x + 48, y), (x + 62, y)])
        s.text(x + 31, y - 16, label, 13)

    def switch_h(s, x, y, label):
        s.line([(x, y), (x + 14, y)]); s.add(f'<circle cx="{x+14}" cy="{y}" r="5" fill="#fff" stroke="{BLK}" stroke-width="3"/>')
        s.line([(x + 14, y), (x + 50, y - 20)]); s.add(f'<circle cx="{x+60}" cy="{y}" r="5" fill="#fff" stroke="{BLK}" stroke-width="3"/>')
        s.line([(x + 65, y), (x + 80, y)]); s.text(x + 40, y + 34, label, 13)

    def estop(s, x, y):  # boton tipo seta, vertical
        s.line([(x, y), (x, y + 18)]); s.line([(x, y + 62), (x, y + 80)])
        s.add(f'<rect x="{x-16}" y="{y+40}" width="32" height="22" fill="#9e1b1b" stroke="{BLK}" stroke-width="2"/>')
        s.add(f'<ellipse cx="{x}" cy="{y+36}" rx="26" ry="16" fill="{RED}" stroke="{BLK}" stroke-width="3"/>')
        s.line([(x, y + 18), (x, y + 24)])
        s.text(x + 40, y + 28, "PARO DE EMERGENCIA\n(seta, corta 36 V)", 13, "start", RED, True)

    def cap_v(s, x, y, label):  # electrolitico, centro en x, y superior
        s.line([(x, y), (x, y + 18)]); s.line([(x - 16, y + 18), (x + 16, y + 18)], w=4)
        s.add(f'<path d="M{x-16},{y+30} Q{x},{y+22} {x+16},{y+30}" fill="none" stroke="{BLK}" stroke-width="4"/>')
        s.line([(x, y + 28), (x, y + 46)]); s.text(x - 20, y + 16, "+", 15, "end", RED, True)
        s.text(x - 22, y + 36, label, 11, "end", GRY)

    def res_v(s, x, y, label):  # zigzag vertical
        pts = [(x, y), (x, y + 8)]
        for i in range(6):
            pts.append((x + (9 if i % 2 == 0 else -9), y + 14 + i * 7))
        pts += [(x, y + 56), (x, y + 64)]
        s.line(pts, w=3); s.text(x + 18, y + 38, label, 13, "start")

    def res_h(s, x, y, label):
        pts = [(x, y), (x + 8, y)]
        for i in range(6):
            pts.append((x + 14 + i * 7, y + (9 if i % 2 == 0 else -9)))
        pts += [(x + 56, y), (x + 64, y)]
        s.line(pts, w=3); s.text(x + 32, y - 16, label, 13)

    def battery(s, x, y):  # vertical, centro (x,y)
        s.line([(x, y - 80), (x, y - 20)]); s.line([(x - 30, y - 20), (x + 30, y - 20)], w=5)
        s.line([(x - 18, y - 6), (x + 18, y - 6)], w=3); s.line([(x - 30, y + 8), (x + 30, y + 8)], w=5)
        s.line([(x - 18, y + 22), (x + 18, y + 22)], w=3); s.line([(x, y + 22), (x, y + 80)])
        s.text(x - 14, y - 26, "+", 18, "end", RED, True); s.text(x + 40, y + 2, "Bateria\nhoverboard\n36 V", 13, "start", bold=True)

    def servo(s, x, y, title, sig):  # cuerpo azul con horn y 3 cables hacia abajo? (x,y = esquina sup izq)
        s.add(f'<rect x="{x}" y="{y}" width="120" height="64" rx="6" fill="#263238" stroke="{BLK}" stroke-width="2.5"/>')
        s.add(f'<rect x="{x-16}" y="{y+18}" width="16" height="28" fill="#455a64" stroke="{BLK}" stroke-width="2"/>')
        s.add(f'<rect x="{x+120}" y="{y+18}" width="16" height="28" fill="#455a64" stroke="{BLK}" stroke-width="2"/>')
        s.add(f'<circle cx="{x+88}" cy="{y+32}" r="15" fill="#eceff1" stroke="{BLK}" stroke-width="2"/>')
        s.add(f'<circle cx="{x+88}" cy="{y+32}" r="4" fill="{BLK}"/>')
        s.line([(x + 88, y + 32), (x + 88, y - 30)], "#eceff1", 8); s.line([(x + 88, y + 32), (x + 88, y - 30)], BLK, 2)
        s.text(x + 34, y + 38, "SERVO", 12, c="#fff", bold=True)
        s.text(x + 60, y + 90, title, 13, bold=True)

    def buck(s, x, y, w, title, sub):
        s.add(f'<rect x="{x}" y="{y}" width="{w}" height="86" rx="6" fill="#1565c0" stroke="{BLK}" stroke-width="2.5"/>')
        s.add(f'<rect x="{x+w/2-26}" y="{y+22}" width="52" height="38" fill="#cfd8dc" stroke="{BLK}" stroke-width="2"/>')
        s.add(f'<circle cx="{x+w/2+40}" cy="{y+40}" r="11" fill="#ffd54f" stroke="{BLK}" stroke-width="2"/>')
        s.text(x + w / 2, y + 16, title, 13, c="#fff", bold=True)
        s.text(x + w / 2, y + 76, sub, 11, c="#fff")
        s.text(x + 8, y + 62, "IN+", 11, "start", "#ffcdd2"); s.text(x + w - 8, y + 62, "OUT+", 11, "end", "#ffcdd2")

    def save(s, name):
        open(name, "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s.w} {s.h}" width="{s.w}" height="{s.h}">'
                              f'<rect width="100%" height="100%" fill="#fff"/>{"".join(s.o)}</svg>')


# =============== 1. POTENCIA ===============
g = SVG(2250, 1020)
g.text(20, 34, "Calavera robotica - distribucion de potencia", 22, "start", bold=True)
g.text(20, 58, "ESQUEMA DE PROPUESTA: valores a medir/verificar antes de energizar. Todas las masas son comunes (riel inferior).", 13, "start", GRY)
BUS, GY = 130, 920
g.battery(90, 400)
g.line([(90, 320), (90, BUS)], RED); g.line([(90, 480), (90, GY)], BLK)
g.fuse_h(90, BUS, "F1 15 A"); g.line([(90, BUS), (90, BUS)])
g.switch_h(170, BUS, "INTERRUPTOR\nGENERAL 36 V DC")
g.line([(250, BUS), (800, BUS)], RED, 4); g.text(330, BUS - 12, "Bus +36 V", 14, "start", RED, True)
g.line([(90, GY), (2130, GY)], BLK, 4); g.text(20, GY + 40, "GND comun", 13, "start", bold=True); g.gnd(90, GY)

# Rama A
xa = 430
g.text(xa, 100, "RAMA A - MOTORES", 15, c=GRY, bold=True)
g.dot(xa, BUS, RED); g.line([(xa, BUS), (xa, BUS + 20)], RED)
g.estop(xa, BUS + 20)
g.line([(xa, BUS + 100), (xa, 330)], RED)
g.box(xa - 110, 330, 220, 130, "2 placas hoverboard", "derecha (ID 0) + izquierda (ID 1)", "#fff8e1")
g.text(xa, 396, "Las dos a 36 V en paralelo,\nSIN cable maestro-esclavo", 11, "middle", GRY)
g.text(xa, 432, "UART propio por placa -> ESP32\nArranque: unir 2 pines del boton", 11, "middle", BLU, True)
g.line([(xa, 460), (xa, GY)], BLK); g.dot(xa, GY)
g.text(xa, 500, "Sin Jetson ni servos aqui: si se pulsa\nel paro, estos siguen vivos", 12, c=GRY)

# Rama B: SZDULI 12 V -> servos, Jetson, hub
xb = 800
g.text(xb + 300, 100, "RAMA B - 12 V: SERVOS, CEREBRO Y HUB", 15, c=GRY, bold=True)
g.dot(xb, BUS, RED); g.line([(xb, BUS), (xb, BUS + 20)], RED)
g.fuse_v(xb, BUS + 20, "F2 8-10 A DC"); g.line([(xb, BUS + 82), (xb, 260)], RED)
g.buck(xb - 130, 260, 260, "SZDULI 18-75 V -> 12 V", "15 A max (180 W) - fija 12 V")
g.line([(xb - 130, 300), (xb - 190, 300), (xb - 190, GY)], BLK); g.dot(xb - 190, GY)
g.line([(xb + 130, 300), (xb + 170, 300), (xb + 170, 420)], RED, 4)
R12 = 420
g.line([(xb + 170, R12), (2080, R12)], RED, 4); g.text(xb + 180, R12 - 10, "Riel +12 V (cond. 1000 uF)", 13, "start", RED, True)

# un buck XL4015 por servo (12 V -> 5 V)
R6 = 640
for i, (nm, gp) in enumerate([("Servo GIRO", "GPIO13"), ("Servo CABECEO", "GPIO14")]):
    bx = 1100 + i * 330
    g.dot(bx, R12, RED); g.line([(bx, R12), (bx, 460)], RED)
    g.buck(bx - 110, 460, 220, f"XL4015 {i+1}: 12 V -> 5 V", "5 A - ajustar 5,0 V y medir")
    g.line([(bx - 110, 500), (bx - 215, 500), (bx - 215, GY)], BLK); g.dot(bx - 215, GY)
    g.line([(bx + 110, 500), (bx + 140, 500), (bx + 140, R6)], RED, 4)
    g.line([(bx - 90, R6), (bx + 140, R6)], RED, 4)
    cx = bx - 20
    g.dot(cx, R6, RED); g.line([(cx, R6), (cx, 710)], RED)
    g.cap_v(cx - 70, R6, "470-1000 uF"); g.line([(cx - 70, R6), (cx, R6)], RED)
    g.line([(cx - 70, R6 + 46), (cx - 70, GY)], BLK); g.dot(cx - 70, GY)
    g.servo(cx - 50, 710, nm, gp)
    g.line([(cx + 70, 750), (cx + 70, GY)], "#6d4c41"); g.dot(cx + 70, GY)
    g.line([(cx + 98, 710), (cx + 98, 680)], ORG, 3); g.text(cx + 98, 672, f"senal {gp}", 11, "middle", ORG, True)
g.text(1640, 790, "Servos: V+ y GND\nsolo de su buck,\nNO del ESP32", 11, c=GRY)

# Jetson
xj = 1790
g.dot(xj, R12, RED); g.line([(xj, R12), (xj, 470)], RED)
g.box(xj - 100, 470, 200, 110, "Jetson Orin Nano", "jack DC (12 V, polaridad a medir)", "#e8f5e9", "#2e7d32")
g.text(xj, 562, "4 USB -> hub alimentado", 11, c=GRY)
g.line([(xj, 580), (xj, GY)], BLK); g.dot(xj, GY)

# hub
xh = 2010
g.dot(xh, R12, RED); g.line([(xh, R12), (xh, 460)], RED)
g.buck(xh - 70, 460, 140, "12 V -> 5 V", "OPCIONAL")
g.line([(xh - 70, 500), (xh - 100, 500), (xh - 100, GY)], BLK); g.dot(xh - 100, GY)
g.line([(xh + 70, 500), (xh + 95, 500), (xh + 95, 600)], RED, 3)
g.box(xh - 70, 600, 140, 70, "Hub USB", "por la Jetson (o buck)", "#e8f5e9", "#2e7d32")
g.line([(xh - 35, 670), (xh - 35, GY)], BLK); g.dot(xh - 35, GY)
g.text(xh, 700, "-> C922, ESP32 ojos,\nESP32 cuello, parlantes", 11, c=GRY)

# leyenda
g.line([(20, 985), (60, 985)], RED, 4); g.text(70, 990, "+ (36 / 12 / 5 V)", 12, "start")
g.line([(240, 985), (280, 985)], BLK, 4); g.text(290, 990, "GND comun", 12, "start")
g.line([(400, 985), (440, 985)], ORG, 3); g.text(450, 990, "senal", 12, "start")
# calibres de cable
def awg(x, y, t, anchor="start"):
    g.add(f'<rect x="{x-2 if anchor=="start" else x-52}" y="{y-13}" width="54" height="18" rx="4" fill="#fffde7" stroke="#f9a825"/>')
    g.text(x + 25 if anchor == "start" else x - 25, y, t, 11, "middle", "#6d4c00", True)
awg(100, 230, "14 AWG")            # bateria -> interruptor
awg(520, BUS - 24, "14 AWG")       # bus 36 V
awg(442, 300, "14 AWG")            # rama A al hoverboard
awg(812, 215, "14 AWG")            # rama B a SZDULI
awg(1010, R12 - 28, "16 AWG")      # riel 12 V
for i in range(2):
    bx = 1100 + i * 330
    awg(bx + 6, 442, "16 AWG")     # entrada del buck
    awg(bx + 148, 590, "18 AWG")   # salida del buck al servo
awg(xj + 6, 445, "16 AWG")         # Jetson
awg(120, GY - 14, "14 AWG")        # retorno de masa principal
g.add('<text x="20" y="1006" font-size="12" fill="#555" font-family="Helvetica,Arial,sans-serif">Calibres: 14 AWG = 36 V (hasta 15 A) | 16 AWG = riel 12 V | 18 AWG = 5 V a servos | 20-22 AWG = masa corta y senales</text>')
g.save("power_diagram.svg")

# =============== 2. SENALES ESP32 CUELLO ===============
n = SVG(1500, 1010)
n.text(20, 34, "ESP32-WROOM del cuello - senales (cuello, 2 placas hoverboard, ultrasonido, paro)", 22, "start", bold=True)
n.text(20, 58, "Pines GPIO evitan los de arranque. Hoverboard: 2 placas Gen2.x (layout 2.2.3), CADA UNA con su UART (REMOTE_UARTBUS, 19200 baudios): derecha UART2, izquierda UART1.", 13, "start", GRY)
ex, ey, ew, eh = 560, 110, 280, 770
n.box(ex, ey, ew, eh, "ESP32-WROOM", "modulo cuello/hoverboard", "#e3f2fd", "#1565c0")
pins_l = [("USB (a hub/Jetson)", 220), ("GND", 600), ("5V / VIN", 700)]
for t, y in pins_l:
    n.line([(ex - 40, y), (ex, y)]); n.text(ex + 12, y + 5, t, 13, "start")
pins_r = [("GPIO13", 190, ORG), ("GPIO14", 270, ORG), ("GPIO16 (RX2)", 350, BLU), ("GPIO17 (TX2)", 400, BLU),
          ("GPIO19 (RX1)", 460, BLU), ("GPIO21 (TX1)", 510, BLU),
          ("GPIO25 (TRIG)", 620, ORG), ("GPIO26 (ECHO)", 700, ORG), ("GPIO27", 810, ORG)]
for t, y, c in pins_r:
    n.line([(ex + ew, y), (ex + ew + 40, y)], c); n.text(ex + ew - 12, y + 5, t, 13, "end")

# izquierda: USB y GND/5V
n.box(60, 185, 240, 70, "Hub USB -> Jetson", "cable USB (datos + 5 V)", "#e8f5e9", "#2e7d32")
n.line([(300, 220), (ex - 40, 220)], GRN, 4)
n.line([(ex - 40, 600), (320, 600)], BLK, 4); n.gnd(320, 600); n.text(310, 575, "GND comun\n(borne comun)", 12, "end", GRY)
n.line([(ex - 40, 700), (330, 700)], RED, 4); n.text(320, 690, "5 V del USB\n(para el HC-SR04)", 12, "end", GRY)

# servos
rx = ex + ew + 40
for y, nm in [(190, "Servo GIRO\nMG996R"), (270, "Servo CABECEO")]:
    n.line([(rx, y), (rx + 150, y)], ORG, 3)
    n.servo(rx + 150, y - 32, "", "")
    n.text(rx + 290, y + 4, nm, 13, "start", bold=True)
n.text(rx + 150, 318, "V+ (5-6 V del buck) y GND: NO del ESP32", 12, "start", RED, True)

# hoverboard: dos placas, un UART cada una
n.line([(rx, 350), (rx + 200, 350)], BLU, 3); n.line([(rx, 400), (rx + 200, 400)], BLU, 3)
n.box(rx + 200, 325, 250, 110, "Placa DERECHA (ID 0)", "", "#fff8e1")
n.text(rx + 215, 372, "PB6 (TX)", 12, "start", BLU, True); n.text(rx + 215, 422, "PB7 (RX)", 12, "start", BLU, True)
n.text(rx + 100, 342, "GPIO16 <- PB6", 12, c=BLU, bold=True); n.text(rx + 100, 392, "GPIO17 -> PB7", 12, c=BLU, bold=True)
n.line([(rx, 460), (rx + 200, 460)], BLU, 3); n.line([(rx, 510), (rx + 200, 510)], BLU, 3)
n.box(rx + 200, 445, 250, 110, "Placa IZQUIERDA (ID 1)", "", "#fff8e1")
n.text(rx + 215, 492, "PB6 (TX)", 12, "start", BLU, True); n.text(rx + 215, 542, "PB7 (RX)", 12, "start", BLU, True)
n.text(rx + 100, 452, "GPIO19 <- PB6", 12, c=BLU, bold=True); n.text(rx + 100, 502, "GPIO21 -> PB7", 12, c=BLU, bold=True)
n.text(rx + 200, 574, "Layout 2.2.3, USART0 PB6/PB7. GND comun obligatorio\ncon las 2 placas. Cada una responde a su SLAVE_ID (0 y 1).", 11, "start", GRY)

# ultrasonido con divisor
n.line([(rx, 620), (rx + 150, 620)], ORG, 3)
n.box(rx + 150, 600, 250, 80, "HC-SR04", "", "#f3e5f5", "#6a1b9a")
n.add(f'<circle cx="{rx+210}" cy="{636}" r="20" fill="#cfd8dc" stroke="{BLK}" stroke-width="2.5"/>')
n.add(f'<circle cx="{rx+340}" cy="{636}" r="20" fill="#cfd8dc" stroke="{BLK}" stroke-width="2.5"/>')
n.text(rx + 275, 698, "VCC a 5 V, GND comun (no dibujado)", 11, c=GRY)
# ECHO: 5V -> R1 -> nodo -> GPIO26 ; nodo -> R2 -> GND
n.line([(rx + 400, 660), (rx + 430, 660), (rx + 430, 690)], ORG, 3)
n.res_v(rx + 430, 690, "R1 1 k")
n.line([(rx + 430, 754), (rx + 430, 770)], ORG, 3); n.dot(rx + 430, 770, ORG)
n.line([(rx + 430, 770), (rx, 770), (rx, 700)], ORG, 3)
n.text(rx + 215, 762, "nodo -> GPIO26 (3,3 V max)", 12, c=ORG, bold=True)
n.res_v(rx + 430, 770, "R2 2 k")
n.line([(rx + 430, 834), (rx + 430, 860)], BLK, 3); n.gnd(rx + 430, 860)
n.text(rx + 450, 670, "ECHO saca 5 V:\ndivisor 1k/2k\nobligatorio", 11, "start", RED, True)

# paro
n.line([(rx, 810), (rx + 150, 810)], ORG, 3)
n.box(rx + 150, 800, 240, 70, "Contacto auxiliar del paro", "a GND (pull-up interna)", "#ffebee", "#c62828")
n.text(rx + 150, 925, "Solo SENAL para el firmware; el corte real de 36 V\nlo hace el paro en la rama A (ver power_diagram).", 12, "start", GRY)
n.save("neck_signals.svg")
print("ok")

# =============== 3. MAPA USB ===============
u = SVG(1300, 700)
u.text(20, 34, "Mapa USB de la Jetson Orin Nano", 22, "start", bold=True)
u.text(20, 58, "Bluetooth: ya integrado en la Jetson (bluetoothctl lo lista), no hace falta dongle.", 13, "start", GRY)
u.box(60, 100, 280, 470, "Jetson Orin Nano", "carrier board", "#e8f5e9", "#2e7d32")
ports = [("USB-A 1 (USB 3)", 190), ("USB-A 2", 260), ("USB-A 3", 330), ("USB-A 4", 400), ("USB-C (a verificar: host)", 500)]
for t, y in ports:
    u.add(f'<rect x="300" y="{y-14}" width="40" height="28" fill="#cfd8dc" stroke="{BLK}" stroke-width="2"/>')
    u.text(290, y + 5, t, 12, "end")
devs = [(190, "Camara Logitech C922", "video + microfono", "#fff8e1", GRN),
        (260, "ESP32 ojos (CP2102)", "TFT, IMU, LEDs - puerto fijo", "#e3f2fd", BLU),
        (330, "ESP32 cuello (WROOM)", "servos, hoverboard, sonar - puerto fijo", "#e3f2fd", BLU),
        (400, "Libre", "teclado/SSD para configurar", "#f5f5f5", GRY)]
for y, t, sub, f, c in devs:
    u.line([(340, y), (560, y)], c, 4)
    u.box(560, y - 30, 330, 60, t, sub, f)
u.line([(340, 500), (560, 500)], GRN, 4)
u.box(560, 450, 330, 100, "Hub USB (3 puertos A)", "alimentado por la Jetson (buck 5 V opcional)", "#e8f5e9", "#2e7d32")
for i, (t, sub) in enumerate([("Adaptador de audio USB", "-> jack 3,5 mm -> parlantes"),
                              ("Alimentacion parlantes", "solo 5 V (si la Jetson no alcanza: buck 5 V)"),
                              ("Libre", "repuesto")]):
    y = 440 + i * 70 + 90 if False else 480 + i * 70
    u.line([(890, 470 + i * 30), (960, y)], GRN, 3)
    u.box(960, y - 28, 300, 56, t, sub, "#fff8e1" if i < 2 else "#f5f5f5")
u.text(60, 640, "Nombres estables de los ESP32: usar /dev/serial/by-path/... (mismo chip en ambos) y conectar siempre cada uno al mismo puerto.", 12, "start", GRY)
u.save("usb_map.svg")

# =============== 4. PERFBOARD DEL ESP32 CUELLO ===============
P, X0, Y0 = 34, 120, 130
COLS = "ABCDEFGHIJKLMNOPQRSTUVWX"
b = SVG(1560, 1010)


def H(c, r):
    return (X0 + COLS.index(c) * P, Y0 + (r - 1) * P)


def wire(pts, color, dash=None, w=4):
    xy = [H(c, r) if isinstance(c, str) else (c, r) for c, r in pts]
    b.line(xy, color, w, dash)
    for p in (xy[0], xy[-1]):
        b.dot(p[0], p[1], color)


b.text(20, 34, "Perfboard del ESP32 del cuello (24 x 18 agujeros) - disposicion SUGERIDA", 22, "start", bold=True)
b.text(20, 58, "Supone ESP32 DevKit de 30 pines con USB hacia la derecha. Verificar el pinout de TU placa antes de soldar. Cruces de cables = por la cara de soldadura.", 12, "start", GRY)
b.text(20, 76, "Fila inferior (izq. a der.): EN VP VN 34 35 32 33 25 26 27 14 12 13 GND VIN.  Fila superior (izq. a der.): 23 22 TX0 RX0 21 19 18 5 17 16 4 2 15 GND 3V3  (orden indicado por el usuario con su placa).", 12, "start", GRY)
# tablero
bx0, by0 = X0 - 30, Y0 - 30
b.add(f'<rect x="{bx0}" y="{by0}" width="{23*P+60}" height="{17*P+60}" rx="10" fill="#e8dcc0" stroke="#8d6e63" stroke-width="3"/>')
for ci, cl in enumerate(COLS):
    b.text(X0 + ci * P, by0 - 6, cl, 11, c=GRY)
for r in range(1, 19):
    b.text(bx0 - 8, Y0 + (r - 1) * P + 4, str(r), 11, "end", GRY)
    for ci in range(24):
        b.add(f'<circle cx="{X0+ci*P}" cy="{Y0+(r-1)*P}" r="3" fill="#6d4c41"/>')
# ESP32
x1, y1 = H("D", 4); x2, y2 = H("R", 13)
b.add(f'<rect x="{x2+14}" y="{H("R",7)[1]}" width="46" height="{3*P}" rx="4" fill="#b0bec5" stroke="{BLK}" stroke-width="2"/>')
b.text(x2 + 37, H("R", 8)[1] + 8, "USB", 11, c="#37474f", bold=True)
b.add(f'<rect x="{x1-16}" y="{y1-16}" width="{x2-x1+32}" height="{y2-y1+32}" rx="8" fill="#bbdefb" stroke="#1565c0" stroke-width="2.5" opacity="0.88"/>')
b.text((x1 + x2) / 2, (y1 + y2) / 2 - 8, "ESP32 DevKit (30 pines)", 15, bold=True)
b.text((x1 + x2) / 2, (y1 + y2) / 2 + 12, "cuello + hoverboard + sonar", 12, c=GRY)
top = ["23", "22", "TX0", "RX0", "21", "19", "18", "5", "17", "16", "4", "2", "15", "GND", "3V3"]   # fila superior, de izq. a der., USB a la derecha (confirmado con la placa real)
bot = ["EN", "VP", "VN", "34", "35", "32", "33", "25", "26", "27", "14", "12", "13", "GND", "VIN"]
used_top = {"3V3": "#2e7d32", "GND": BLK, "16": BLU, "17": BLU, "19": BLU, "21": BLU}
used_bot = {"25": ORG, "26": ORG, "27": ORG, "14": ORG, "13": ORG, "GND": BLK, "VIN": RED}
for i in range(15):
    c = COLS[3 + i]
    px, py = H(c, 4); qx, qy = H(c, 13)
    uc = used_top.get(top[i]); ub = used_bot.get(bot[i])
    b.add(f'<circle cx="{px}" cy="{py}" r="8" fill="{uc or "#eceff1"}" stroke="{BLK}" stroke-width="1.5"/>')
    b.add(f'<circle cx="{qx}" cy="{qy}" r="8" fill="{ub or "#eceff1"}" stroke="{BLK}" stroke-width="1.5"/>')
    b.text(px, py + 25, top[i], 10, c="#0d47a1", bold=bool(uc))
    b.text(qx, qy - 14, bot[i], 10, c="#0d47a1", bold=bool(ub))


def pin(c, r, color="#263238"):
    x, y = H(c, r)
    b.add(f'<rect x="{x-8}" y="{y-8}" width="16" height="16" fill="{color}" stroke="{BLK}" stroke-width="1.5"/>')


# --- Hoverboard (arriba)
for c, lab, col in [("H", "PB7 RX", BLU), ("I", "PB6 TX", BLU), ("J", "GND", BLK), ("L", "PB7 RX", BLU), ("M", "PB6 TX", BLU), ("N", "GND", BLK)]:
    pin(c, 2, col)
b.text(H("H", 1)[0] - 14, H("H", 1)[1] - 12, "IZQUIERDA (ID 1): H-J", 11, "start", BLU, True)
b.text(H("L", 1)[0] - 14, H("L", 1)[1] - 12, "DERECHA (ID 0): L-N", 11, "start", BLU, True)
wire([("H", 2), ("H", 4)], BLU); wire([("I", 2), ("I", 4)], BLU)      # izquierda: PB7 <- GPIO21, PB6 -> GPIO19
wire([("L", 2), ("L", 4)], BLU); wire([("M", 2), ("M", 4)], BLU)      # derecha:   PB7 <- GPIO17, PB6 -> GPIO16
wire([("N", 2), ("N", 3), ("Q", 3), ("Q", 4)], BLK)                    # GND derecha -> GND superior del ESP32
wire([("J", 2), ("J", 1), ("Q", 1), ("Q", 3)], BLK)                    # GND izquierda -> GND superior (por la fila 1)
# --- 3V3 libre (D4)
# --- Servos (fila 16)
for c, lab, col in [("L", "GND", BLK), ("M", "V+", RED), ("N", "SIG", ORG)]:
    pin(c, 16, col)
for c, lab, col in [("P", "SIG", ORG), ("Q", "V+", RED), ("R", "GND", BLK)]:
    pin(c, 16, col)
wire([("N", 13), ("N", 16)], ORG); wire([("P", 13), ("P", 16)], ORG)
# --- Paro (GPIO27 = M13)
pin("T", 14); pin("U", 14, BLK)
b.text(H("T", 14)[0] - 14, H("T", 14)[1] + 32, "PARO", 11, "start", ORG, True)
wire([("M", 13), ("M", 14), ("T", 14)], ORG)
# --- Sonar: header a la izquierda, fila 16
for c, lab, col in [("D", "VCC", RED), ("E", "TRIG", ORG), ("F", "ECHO", ORG), ("G", "GND", BLK)]:
    pin(c, 16, col)
wire([("E", 16), ("E", 15), ("K", 15), ("K", 13)], ORG)                      # TRIG
wire([("D", 16), ("D", 17), ("S", 17), ("S", 13), ("R", 13)], RED, "6 4")    # VCC desde VIN
# divisor
rx1, ry1 = H("F", 17)
b.add(f'<rect x="{H("F",17)[0]+20}" y="{H("F",17)[1]-9}" width="{3*P-40}" height="18" fill="#d7ccc8" stroke="{BLK}" stroke-width="2"/>')
b.text((H("F", 17)[0] + H("I", 17)[0]) / 2, H("F", 17)[1] - 14, "R1 1 k", 12)
wire([("F", 16), ("F", 17), ("I", 17)], ORG)
wire([("I", 17), ("I", 14), ("L", 14), ("L", 13)], ORG, "6 4")             # nodo -> GPIO26
b.add(f'<rect x="{H("J",16)[0]-9}" y="{H("J",16)[1]+14}" width="18" height="{P+12}" fill="#d7ccc8" stroke="{BLK}" stroke-width="2"/>')
b.text(H("J", 16)[0] + 20, H("J", 17)[1] + 4, "R2 2 k", 12, "start")
wire([("I", 17), ("J", 17), ("J", 18)], ORG)
for c, t in zip("DEFG", ["VCC", "TRIG", "ECHO", "GND"]): b.text(H(c, 16)[0], H(c, 16)[1] - 13, t, 9, c="#263238", bold=True)
for c, t in zip("LMN", ["GND", "V+", "SIG"]): b.text(H(c, 16)[0], H(c, 16)[1] - 13, t, 9, c="#263238", bold=True)
for c, t in zip("PQR", ["SIG", "V+", "GND"]): b.text(H(c, 16)[0], H(c, 16)[1] - 13, t, 9, c="#263238", bold=True)
for c, t in zip("HIJLMN", ["PB7", "PB6", "GND", "PB7", "PB6", "GND"]): b.text(H(c, 2)[0], H(c, 2)[1] - 13, t, 9, c="#263238", bold=True)
# --- Masa
wire([("D", 18), ("X", 18)], BLK, w=6)
b.text(H("D", 18)[0] - 8, H("D", 18)[1] + 24, "Riel de masa (GND comun)", 12, "start", bold=True)
wire([("G", 16), ("G", 18)], BLK); wire([("L", 16), ("L", 18)], BLK); wire([("R", 16), ("R", 18)], BLK)
wire([("U", 14), ("U", 18)], BLK)
wire([("Q", 13), ("T", 13), ("T", 18)], BLK)
wire([("J", 18), ("J", 18)], BLK)
# condensadores 1000 uF (simbolo) junto a cada servo
for c1, c2, nm in [("M", "L", "C1"), ("Q", "R", "C2")]:
    xa, ya = H(c1, 17); xb_, yb = H(c2, 17)
    b.line([(H(c1, 16)[0], H(c1, 16)[1]), (xa, ya)], RED, 3)
    b.add(f'<rect x="{min(xa,xb_)-4}" y="{ya-12}" width="{abs(xa-xb_)+8}" height="24" rx="12" fill="#37474f" stroke="{BLK}" stroke-width="2"/>')
    b.text((xa + xb_) / 2, ya + 5, f"{nm} 1000uF", 9, c="#fff", bold=True)
    b.line([(xb_, yb), (xb_, H(c2, 18)[1])], BLK, 3)

# zonas planas (16)
zy = Y0 + 17 * P + 60
b.text(X0 - 20, zy - 8, "16 zonas planas para soldar (entradas de potencia). Asignacion sugerida:", 13, "start", bold=True)
zones = [("Z1", "+5V buck GIRO", RED), ("Z2", "GND buck GIRO", BLK), ("Z3", "+5V buck CABECEO", RED), ("Z4", "GND buck CABECEO", BLK),
         ("Z5", "GND masa comun\n(SZDULI OUT-)", BLK), ("Z6", "GND hoverboard", BLK), ("Z7", "libre", GRY), ("Z8", "libre", GRY)]
zones += [(f"Z{i}", "libre", GRY) for i in range(9, 17)]
for i, (z, t, col) in enumerate(zones):
    x = X0 - 20 + (i % 8) * 128; y = zy + (i // 8) * 70
    b.add(f'<rect x="{x}" y="{y}" width="112" height="52" rx="6" fill="#ffe0b2" stroke="{col}" stroke-width="3"/>')
    b.text(x + 56, y + 20, z, 13, bold=True)
    b.text(x + 56, y + 36, t, 10, c=col)
# leyenda
ly = 60
for i, (t, col) in enumerate([("+5 V servos", RED), ("GND", BLK), ("Senal", ORG), ("UART hoverboard", BLU)]):
    b.line([(1180, 100 + i * 24), (1220, 100 + i * 24)], col, 4); b.text(1230, 104 + i * 24, t, 12, "start")
# tabla de conexiones
rows = [
    ("GPIO13 (P13)", "Servo giro, SIG (P16)"),
    ("GPIO14 (N13)", "Servo cabeceo, SIG (N16)"),
    ("GPIO16 (M4)", "PB6 TX placa DERECHA (M2)"),
    ("GPIO17 (L4)", "PB7 RX placa DERECHA (L2)"),
    ("GPIO19 (I4)", "PB6 TX placa IZQUIERDA (I2)"),
    ("GPIO21 (H4)", "PB7 RX placa IZQUIERDA (H2)"),
    ("GPIO25 (K13)", "Sonar TRIG (E16)"),
    ("GPIO26 (L13)", "Nodo del divisor R1/R2"),
    ("GPIO27 (M13)", "Paro, contacto a GND (T14)"),
    ("VIN (R13)", "Sonar VCC (D16)"),
    ("GND (Q13, Q4)", "Riel de masa"),
]
b.text(1180, 230, "Conexiones ESP32 -> destino", 13, "start", bold=True)
for i, (a, d_) in enumerate(rows):
    b.text(1180, 254 + i * 20, f"{a}  ->  {d_}", 11, "start")
b.text(1180, 600, "Cabeceras (fila 16): D-G sonar [VCC,TRIG,ECHO,GND];", 11, "start")
b.text(1180, 618, "L-N servo cabeceo [GND,V+,SIG] (enchufar al reves);", 11, "start")
b.text(1180, 636, "P-R servo giro [SIG,V+,GND]; T-U paro (fila 14);", 11, "start")
b.text(1180, 654, "H-J placa izquierda y L-N derecha (fila 2): PB7, PB6, GND;", 11, "start")
b.text(1180, 672, "el GND de cada placa va al GND superior del ESP32 (Q4).", 11, "start")
b.text(1180, 690, "C1/C2 = 1000 uF entre V+ y GND.", 11, "start")
b.text(1180, 490, "V+ de cada servo: de su buck (Z1 / Z3),", 11, "start", RED, True)
b.text(1180, 508, "NO del ESP32. GND de bucks al riel.", 11, "start", RED, True)
b.text(1180, 540, "Divisor: ECHO -> R1 1k -> nodo -> GPIO26;", 11, "start")
b.text(1180, 558, "nodo -> R2 2k -> GND.", 11, "start")
b.save("board_layout.svg")


# =============== 5. PLACAS DEL HOVERBOARD: CONECTORES Y PINES ===============
h = SVG(1760, 1290)
VER, LAY = "#2e7d32", "#8d6e00"
h.text(20, 34, "Placas del hoverboard SMART-L-V2.1 (STM32F103C8T6, LQFP48): conectores, pines y estado", 22, "start", bold=True)
h.text(20, 58, "Dos placas iguales, una por rueda. Firmware: Gen2.x de RoboDurden, layout 2.2.3 (TARGET 2, SINGLE, REMOTE_UARTBUS, BLDC_BC, compuertas activas en BAJO). Verde = verificado en las placas (8 nov); ocre = tomado del layout, sin comprobar aparte.", 12, "start", GRY)

# --- A. dibujo de la placa (orientacion de la foto anotada: zumbador a la izquierda) ---
bx, by, bw, bh = 40, 110, 760, 430
h.add(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="14" fill="#c62828" stroke="#7f0000" stroke-width="4"/>')
h.text(bx + 22, by + 34, "SMART-L-V2.1", 22, "start", "#ffcdd2", True)

def conn(x, y, w, hh, title, sub, col, filled="#fffde7"):
    h.add(f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" rx="6" fill="{filled}" stroke="{col}" stroke-width="3"/>')
    h.text(x + w / 2, y + 20, title, 13, bold=True)
    for i, ln in enumerate(sub.split("\\n")):
        h.text(x + w / 2, y + 38 + i * 15, ln, 11, c="#444")

conn(bx + 20, by + 60, 150, 58, "LED", "no usado en este layout", LAY)
conn(bx + 20, by + 128, 190, 98, "SWD  (J5)", "1 (pad cuadrado) 3V3\\n2 GND   3 SWDIO   4 SWCLK\\n4 agujeros junto al zumbador", VER)
h.add(f'<circle cx="{bx+70}" cy="{by+290}" r="38" fill="#263238" stroke="#000" stroke-width="3"/>')
h.text(bx + 70, by + 296, "zumbador", 11, c="#fff", bold=True)
conn(bx + 215, by + 250, 150, 132, "USART", "6 pines junto al chip\\nPB6 (TX placa)\\nPB7 (RX placa)\\nGND\\n(medir con multimetro)", VER)
conn(bx + 20, by + 340, 170, 74, "Gyro (etiqueta del foro)", "el firmware no lo usa;\\nsenales SIN medir (I2C?)", LAY)
conn(bx + 200, by + 392, 110, 30, "3 pines +5V", "", GRY, "#eee")
h.add(f'<rect x="{bx+390}" y="{by+170}" width="120" height="120" rx="8" fill="#212121" stroke="#000" stroke-width="3"/>')
h.text(bx + 450, by + 206, "STM32F103C8T6", 12, c="#fff", bold=True); h.text(bx + 450, by + 224, "LQFP48", 11, c="#bbb")
h.text(bx + 450, by + 244, "cara sin marcas", 11, c="#bbb"); h.text(bx + 450, by + 262, "(ID 0x0410)", 11, c="#bbb")
conn(bx + 380, by + 330, 170, 84, "HALL (5 hilos)", "5 V, GND, HALL A PA0\\nHALL B PA2, HALL C PA1\\n(orden por defecto OK)", VER)
conn(bx + 540, by + 330, 190, 84, "Otra placa (cable plano)", "VCC RXD TXD GND\\nmaestro-esclavo; NO se usa\\ncon UART propio por placa", LAY)
conn(bx + 560, by + 190, 170, 98, "BOTON (2 pines)", "unir 1 s para ARRANCAR\\ny SOLTAR (el firmware\\nespera a que se suelte)", VER)
h.text(bx + 540, by + 78, "Fases del motor:", 12, "start", bold=True)
h.text(bx + 540, by + 96, "3 cables gruesos soldados", 11, "start", c="#ffcdd2")
h.text(bx + 540, by + 112, "amarillo, azul, verde", 11, "start", c="#ffcdd2")
h.text(bx + 540, by + 138, "Bateria 36 V: 2 cables gruesos", 11, "start", c="#ffcdd2")
h.text(bx + 540, by + 154, "rojo/naranja (+) y negro (-)", 11, "start", c="#ffcdd2")
# flechas SWD
h.text(bx, by + bh + 26, "Chip: el ST-Link lo reconoce como F1xx de densidad media (0x0410, 64 KB, 20 KB RAM).", 12, "start", GRY)
h.text(bx, by + bh + 44, "La proteccion de lectura (RDP) venia ACTIVA y se borro: no hay respaldo del firmware original.", 12, "start", GRY)

# --- B. conexiones externas ---
cy = by + bh + 86
h.text(40, cy, "Conexiones externas probadas", 16, "start", bold=True)
rows = [
    ("ST-Link V2 -> J5", ["3.3V -> 1 (3V3) | GND -> 2 | SWDIO -> 3 | SWCLK -> 4.  NUNCA el pin de 5 V.", "Con la bateria DESCONECTADA: el ST-Link alimenta el chip a 3,3 V."]),
    ("ESP32 <-> placa derecha (ID 0)", ["GPIO16 (RX2) <- PB6 | GPIO17 (TX2) -> PB7 | GND comun.", "UART2, 19200 baudios, 3,3 V."]),
    ("ESP32 <-> placa izquierda (ID 1)", ["GPIO19 (RX1) <- PB6 | GPIO21 (TX1) -> PB7 | GND comun.", "UART1 remapeado, 19200 baudios, 3,3 V."]),
    ("Alimentacion de prueba", ["Fuente regulable 36 V / 0.5-1 A, ruedas en el aire.", "Con 12-30 V pita (aviso de bateria baja; umbral 35 V para 10 celdas)."]),
    ("Encendido", ["Ninguna de las dos arranca sola: unir 1 s los 2 pines del boton con la fuente encendida y soltar.", "Sin tramas del ESP32 durante 500 ms: motor deshabilitado (~50 mA a 36 V)."]),
]
for i, (t, ds) in enumerate(rows):
    y = cy + 30 + i * 50
    h.add(f'<rect x="40" y="{y-15}" width="8" height="38" fill="{VER}"/>')
    h.text(58, y, t, 12, "start", bold=True)
    for j, d in enumerate(ds): h.text(58, y + 15 + j * 14, d, 11, "start", c="#333") if j else h.text(58, y + 15, d, 11, "start", c="#333")

# --- C. tabla de pines del MCU ---
tx = 850
h.text(tx, 110, "Pines del MCU usados por el layout 2.2.3", 16, "start", bold=True)
h.text(tx, 130, "Pin datasheet = numeracion estandar LQFP48 (pin 1 en el punto, sentido antihorario).", 11, "start", GRY)
h.text(tx, 146, "Tu conteo = el que usaste al medir (empieza en el 1er pin de la fila inferior, con el punto abajo a la izquierda): real + 12 (mod 48).", 11, "start", GRY)
cols = [("Senal", tx, "start"), ("Pin MCU", tx + 190, "start"), ("Datasheet", tx + 280, "start"), ("Tu conteo", tx + 380, "start"), ("Estado", tx + 480, "start")]
for t, x, a in cols: h.text(x, 176, t, 12, a, bold=True)
h.line([(tx - 6, 182), (tx + 900, 182)], "#999", 2)
def mine(real): return (real + 12 - 1) % 48 + 1
pins = [
    ("SWDIO", "PA13", 34, True, "verificado (J5)"), ("SWCLK", "PA14", 37, True, "verificado (J5)"),
    ("UART remoto TX", "PB6", 42, True, "verificado (ESP32)"), ("UART remoto RX", "PB7", 43, True, "verificado (ESP32)"),
    ("HALL A", "PA0", 10, True, "motor gira suave"), ("HALL C", "PA1", 11, True, "motor gira suave"), ("HALL B", "PA2", 12, True, "motor gira suave"),
    ("BOTON", "PA3", 13, True, "funciona"), ("SELF_HOLD", "PA4", 14, True, "funciona"),
    ("VBATT (ADC)", "PA5", 15, True, "lee ~35 V con 36 V"), ("CORRIENTE DC (ADC)", "PA7", 17, False, "offset ~0.18 A en reposo"),
    ("ZUMBADOR", "PB1", 19, True, "suena"),
    ("Fase C (amarillo) alta", "PA8", 29, True, "motor gira"), ("Fase B (azul) alta", "PA9", 30, True, "motor gira"), ("Fase A (verde) alta", "PA10", 31, True, "motor gira"),
    ("Fase C (amarillo) baja", "PB13", 26, True, "motor gira"), ("Fase B (azul) baja", "PB14", 27, True, "motor gira"), ("Fase A (verde) baja", "PB15", 28, True, "motor gira"),
    ("Master-slave TX", "PB10", 21, False, "no se usa"), ("Master-slave RX", "PB11", 22, False, "no se usa"),
    ("IMU I2C SCL", "PB8", 45, False, "sin comprobar si hay IMU"), ("IMU I2C SDA", "PB9", 46, False, "sin comprobar si hay IMU"),
]
for i, (sg, mcu, real, ok, st) in enumerate(pins):
    y = 204 + i * 26
    if i % 2 == 0: h.add(f'<rect x="{tx-6}" y="{y-16}" width="906" height="24" fill="#f5f5f5"/>')
    h.text(tx, y, sg, 12, "start"); h.text(tx + 190, y, mcu, 12, "start", BLU, True)
    h.text(tx + 280, y, str(real), 12, "start"); h.text(tx + 380, y, str(mine(real)), 12, "start")
    h.text(tx + 480, y, st, 11, "start", VER if ok else LAY, True)
h.text(tx, 204 + len(pins) * 26 + 10, "GND real: pines 8, 23, 35 y 47 (en tu conteo: 20, 35, 47 y 11). VDD: 1, 9, 24, 36, 48. Orden de Hall y fases = el del layout 2.2.3, sin permutar.", 10, "start", GRY)

# --- D. telemetria ---
ty = 204 + len(pins) * 26 + 50
h.text(tx, ty, "Telemetria que devuelve cada placa por UART (15 bytes, a la frecuencia de las ordenes, ~40 Hz)", 14, "start", bold=True)
tel = [("Velocidad real", "int16 /100, km/h (de los pulsos de Hall)"), ("Voltaje de bateria", "uint16 /100, V (ADC PA5, calibrado para 10 celdas)"),
       ("Corriente DC", "int16 /100, A (shunt, ADC PA7; hay offset en reposo)"), ("Odometria", "int32, pasos de Hall acumulados (con signo)"),
       ("Opcional: IMU", "gyro XYZ, acel XYZ y temperatura si se compila SEND_IMU_DATA y hay IMU (+14 bytes)")]
for i, (a, d_) in enumerate(tel):
    h.text(tx, ty + 24 + i * 20, a, 12, "start", bold=True); h.text(tx + 170, ty + 24 + i * 20, d_, 11, "start", c="#333")
h.save("hoverboard_pinout.svg")
print("ok 5")
