"""Cuello de 3 servos MG995: giro + dos servos horizontales con bielas (cabeceo y ladeo).

    CAD/.venv/bin/python CAD/make_neck3.py

Mecanismo (el de los cuellos de animatronic de "dos bielas"):
  - GIRO: servo vertical en turntable_base (make_turntable.py); su horn mueve neck3_pan_top.
  - Sobre el plato hay una junta cardan central (poste con horquilla, taco cruzado con perno M4 en Y y
    dos tornillos M3 en X, horquilla colgada de la plataforma). La plataforma puede cabecear y ladearse.
  - Dos servos horizontales, uno a cada lado (+-Y), con el eje hacia fuera. Cada uno lleva una palanca
    (neck3_crank) horizontal hacia atras; una biela vertical (rotulas M3 + varilla roscada) la une a
    la plataforma, DETRAS del pivote. Los dos suben = cabeza cabecea hacia delante; uno sube y otro baja = ladea.
  - Tabla de angulos de servo para cada pose: se imprime al ejecutar (usar en el firmware).
Ferreteria: rotulas de biela M3 (2) + varilla M3 (largo segun L_ROD), tornillos M3 para las palancas,
perno M4 x 30 + tuerca autofrenante (eje Y), 2 tornillos M3 x 12 (eje X), 4+4 tornillos M3 para orejas (ranuras +-1.5 mm).
Orden: plato al horn de giro; servos laterales desde fuera; palancas al horn; poste/taco/plataforma; bielas.
"""
import math
import os
import cadquery as cq
import make_turntable as T

OUT = T.OUT

# ---- geometria de la junta (todas las cotas en el marco del plato: Z=0 cara superior, eje de giro en X=Y=0) ----
Z_P = 46.0              # altura del pivote
BLK = 16.0              # taco cruzado cubico
GAP = 0.5
CHEEK_T = 5.0
Z_PL = Z_P + 16.0       # cara inferior de la plataforma

# ---- servos laterales ----
WT = 6.0
YS = 40.0               # cara exterior de la pared (|Y|)
Z_S = 14.0              # altura del eje del servo lateral
X_S = -18.0             # X del eje del servo lateral (cuerpo hacia -X)
R_H = 34.0              # largo de palanca
ARM_T = 4.0
Y_HORN = YS + (T.SERVO_H - T.FLANGE_Z) + T.HORN_TOP     # cara del horn
Y_BALL = Y_HORN + ARM_T + 2.5                            # centro de la rotula (sobre la cara exterior de la palanca)
X_LUG = X_S - R_H       # la biela cuelga de aqui (punta de la palanca en horizontal)
L_ROD = 42.0            # distancia centro a centro de rotulas, con la palanca horizontal
Z_LUG = Z_S + L_ROD
WALL_TOP = Z_S + 14.0
BODY_CX = T.BODY_CX
SLOT_W = T.EAR_SCREW_D + 2 * T.EAR_SLOT_TOL


def side_wall():
    """Pared del servo lateral en +Y (la de -Y es el espejo). Eje del servo en (X_S, Z_S)."""
    cx = X_S + BODY_CX
    wl = T.FLANGE_L + 2 * T.WALL + 4
    wall = (cq.Workplane("XY").box(wl, WT, WALL_TOP, centered=(True, True, False)).translate((cx, YS - WT / 2, 0)))
    opening = (cq.Workplane("XY").box(T.SERVO_L + 2 * T.FIT, WT + 2, T.SERVO_W + 2 * T.FIT)
               .translate((cx, YS - WT / 2, Z_S)))
    wall = wall.cut(opening)
    for sx in (-1, 1):
        for sz in (-1, 1):
            ex, ez = cx + sx * T.EAR_HOLE_DX / 2, Z_S + sz * T.EAR_HOLE_DY / 2
            slot = cq.Workplane("XY").box(SLOT_W, WT + 2, T.EAR_SCREW_D).translate((ex, YS - WT / 2, ez))
            x_in = ex - sx * (T.NUT_AF / 2 + T.EAR_SLOT_TOL)
            x_out = cx + sx * (wl / 2 + 1)
            nut = (cq.Workplane("XY").box(abs(x_out - x_in), T.NUT_T, T.NUT_AF, centered=False)
                   .translate((min(x_in, x_out), YS - T.NUT_DEPTH - T.NUT_T, ez - T.NUT_AF / 2)))
            wall = wall.cut(slot).cut(nut)
    return wall


def make_pan_top():
    pt = T.PLATE_T
    disc = cq.Workplane("XY").circle(T.PLATE_R).extrude(pt)
    wl = T.FLANGE_L + 2 * T.WALL + 4
    x0, x1 = X_S + BODY_CX - wl / 2, X_S + BODY_CX + wl / 2
    deck = cq.Workplane("XY").box(x1 - x0, 2 * YS, pt, centered=False).translate((x0, -YS, 0))
    plate = disc.union(deck)
    access = cq.Workplane("XY").circle(T.HORN_SCREW_ACCESS / 2).extrude(pt)
    horn_holes = cq.Workplane("XY").polarArray(T.HORN_HOLES_R, 0, 360, 4).circle(T.HORN_HOLE_D / 2).extrude(pt)
    heads = (cq.Workplane("XY", origin=(0, 0, pt - T.HEAD_SCREW_DEPTH)).polarArray(T.HORN_HOLES_R, 0, 360, 4)
             .circle(T.HEAD_SCREW_D / 2).extrude(T.HEAD_SCREW_DEPTH))
    plate = plate.cut(access).cut(horn_holes).cut(heads)

    w = side_wall().translate((0, 0, pt))
    top = plate.union(w).union(w.mirror("XZ"))

    # poste de la junta: base maciza hasta bajo el taco + horquilla (dos mejillas en Y, perno M4 en Y)
    inner = BLK / 2 + GAP
    base = (cq.Workplane("XY").box(24, 2 * (inner + CHEEK_T), Z_P - BLK / 2 - GAP, centered=(True, True, False))
            .translate((0, 0, pt)))
    base = base.cut(cq.Workplane("XY").box(30, 2 * inner, 40, centered=(True, True, False))
                    .translate((0, 0, pt + Z_P - BLK / 2 - GAP - 8)))
    for s in (-1, 1):
        ch = (cq.Workplane("XY").box(13, CHEEK_T, Z_P - BLK / 2 - GAP + BLK / 2 + 6.5, centered=(True, True, False))
              .translate((0, s * (inner + CHEEK_T / 2), pt)))
        base = base.union(ch)
    base = base.cut(cq.Workplane("XZ", origin=(0, 30, pt + Z_P)).circle(4.3 / 2).extrude(60))
    top = top.union(base)
    wires = cq.Workplane("XY").pushPoints([(30, -14), (30, 14)]).circle(T.WIRE_HOLE_D / 2 - 1).extrude(pt)
    return top.cut(wires)


def make_cross():
    """Taco cruzado: agujero pasante en Y (M4) y dos agujeros ciegos en X (M3 autorroscante, 5 mm)."""
    b = cq.Workplane("XY").box(BLK, BLK, BLK)
    b = b.cut(cq.Workplane("XZ").circle(4.3 / 2).extrude(BLK, both=True))
    for s in (-1, 1):
        b = b.cut(cq.Workplane("YZ", origin=(s * BLK / 2, 0, 0)).circle(2.6 / 2).extrude(-s * 5.0))
    return b


def make_platform():
    """Plataforma de la cabeza (cuna) + horquilla en X + dos orejas para las bielas. Imprimir BOCA ABAJO."""
    outer = T.HEAD_FIT + T.LIP_T
    plate = T.head_prism(outer, T.PLATE_T).translate((0, 0, Z_PL))
    lip = (T.head_prism(outer, T.LIP_H).cut(T.head_prism(T.HEAD_FIT, T.LIP_H)).translate((0, 0, Z_PL + T.PLATE_T)))
    wing_w = Y_HORN + ARM_T + 2.0
    wing = (cq.Workplane("XY").box(16, 2 * wing_w, T.PLATE_T, centered=(True, True, False))
            .translate((X_LUG, 0, Z_PL)))
    p = plate.union(wing).union(lip)
    # horquilla colgante: dos mejillas en X con agujero M3 en el eje X del pivote
    inner = BLK / 2 + GAP
    for s in (-1, 1):
        ch = (cq.Workplane("XY").box(CHEEK_T, 11.0, Z_PL - (Z_P - 5.5) + 0.5, centered=(True, True, False))
              .translate((s * (inner + CHEEK_T / 2), 0, Z_P - 5.5)))
        ch = ch.cut(cq.Workplane("YZ", origin=(s * (inner + CHEEK_T), 0, Z_P)).circle(3.4 / 2).extrude(-s * 2 * CHEEK_T))
        p = p.union(ch)
    # orejas de las bielas: placa en XZ en la misma Y que las palancas, agujero M3 en Y
    for s in (-1, 1):
        y_in, y_out = Y_HORN, Y_HORN + ARM_T
        lug = (cq.Workplane("XY").box(12, ARM_T, Z_PL - (Z_LUG - 6) + 0.5, centered=(True, False, False))
               .translate((X_LUG, y_in, Z_LUG - 6)))
        lug = lug.cut(cq.Workplane("XZ", origin=(X_LUG, y_out, Z_LUG)).circle(3.4 / 2).extrude(ARM_T))
        if s < 0:
            lug = lug.mirror("XZ")
        p = p.union(lug)
    wires = (cq.Workplane("XY", origin=(0, 0, Z_PL)).pushPoints([(-30, 0), (30, 0)])
             .circle(T.WIRE_HOLE_D / 2).extrude(T.PLATE_T))
    return p.cut(wires)


def make_crank():
    """Palanca: cubo con los 4 agujeros del horn redondo + brazo de R_H hacia -X con agujero M3 en la punta."""
    hub = cq.Workplane("XZ").circle(T.HORN_D / 2 + 1.5).extrude(-ARM_T)       # extruye hacia +Y
    arm = cq.Workplane("XZ").center(-R_H / 2, 0).rect(R_H, 11.0).extrude(-ARM_T)
    tip = cq.Workplane("XZ").center(-R_H, 0).circle(6.5).extrude(-ARM_T)
    c = hub.union(arm).union(tip)
    c = c.cut(cq.Workplane("XZ").circle(T.HORN_SCREW_ACCESS / 2).extrude(-ARM_T))
    c = c.cut(cq.Workplane("XZ").polarArray(T.HORN_HOLES_R, 0, 360, 4).circle(T.HORN_HOLE_D / 2).extrude(-ARM_T))
    c = c.cut(cq.Workplane("XZ", origin=(-R_H, 0, 0)).circle(3.4 / 2).extrude(-ARM_T))
    return c


def servo_dummy():
    cx = X_S + BODY_CX
    body = (cq.Workplane("XY").box(T.SERVO_L, T.SERVO_H - 6, T.SERVO_W, centered=(True, False, True))
            .translate((cx, YS - T.FLANGE_Z, Z_S)))
    ears = cq.Workplane("XY").box(T.FLANGE_L, 2.5, T.SERVO_W, centered=(True, False, True)).translate((cx, YS, Z_S))
    horn = (cq.Workplane("XZ", origin=(X_S, Y_HORN, Z_S)).circle(T.HORN_D / 2).extrude(T.HORN_TOP))
    return body.union(ears).union(horn)


# ---------------- cinematica ----------------
def rot(p, pitch, roll):
    """Gira el punto p (marco mundo, pivote en (0,0,Z_P)) por roll (eje X) y luego pitch (eje Y)."""
    x, y, z = p[0], p[1], p[2] - Z_P
    cr, sr, cp, sp = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch)
    y, z = y * cr - z * sr, y * sr + z * cr
    x, z = x * cp + z * sp, -x * sp + z * cp
    return (x, y, z + Z_P)


def crank_angle(side, pitch_deg, roll_deg):
    """Angulo de la palanca (0 = horizontal hacia -X, + = punta sube) para la pose; None si no se alcanza."""
    lug = rot((X_LUG, side * Y_BALL, Z_LUG), math.radians(pitch_deg), math.radians(roll_deg))
    best = None
    for i in range(-900, 901):
        a = math.radians(i / 10)
        tip = (X_S - R_H * math.cos(a), side * Y_BALL, Z_S + R_H * math.sin(a))
        d = math.dist(tip, lug)
        err = abs(d - L_ROD)
        if best is None or err < best[0]:
            best = (err, i / 10)
    return best[1] if best[0] < 0.3 else None


def kinematics_table():
    print("pitch(+=hacia delante) roll(+) -> palanca +Y / palanca -Y (grados, 0 = horizontal, + = sube)")
    for pit in (-20, -10, 0, 10, 20):
        for rol in (-10, 0, 10):
            a, b = crank_angle(+1, pit, rol), crank_angle(-1, pit, rol)
            print(f"  pitch {pit:+3d}  roll {rol:+3d}:  {a}  /  {b}")


def export(name, part):
    cq.exporters.export(part, os.path.join(OUT, name + ".step"))
    cq.exporters.export(part, os.path.join(OUT, name + ".stl"))
    bb = part.val().BoundingBox()
    print(f"{name}: {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm")


def main():
    os.makedirs(OUT, exist_ok=True)
    base, top, cross, plat, crank = T.make_base(), make_pan_top(), make_cross(), make_platform(), make_crank()
    export("turntable_base", base)
    export("neck3_pan_top", top)
    export("neck3_cross", cross)
    export("neck3_platform", plat)
    export("neck3_crank", crank)          # imprimir 2 (la de -Y es la misma pieza)
    kinematics_table()

    # montaje y choques en poses extremas
    zoff = T.Z_PLATE
    top_w = top.translate((0, 0, zoff))
    sv = servo_dummy().translate((0, 0, zoff + T.PLATE_T))
    sv = sv.union(sv.mirror("XZ"))
    cr_w = crank.translate((0, Y_HORN, zoff + T.PLATE_T + Z_S))
    cr_w = cr_w.union(cr_w.mirror("XZ"))
    fixed = top_w.union(base).union(sv)
    worst = 0.0
    for pit, rol in ((0, 0), (20, 0), (-20, 0), (0, 10), (0, -10), (20, 10), (-20, -10), (20, -10), (-20, 10)):
        p = (plat.translate((0, 0, -Z_P)).rotate((0, 0, 0), (1, 0, 0), rol).rotate((0, 0, 0), (0, 1, 0), pit)
             .translate((0, 0, Z_P + zoff + T.PLATE_T)))
        # ojo: rotate X primero y Y despues = misma convencion que rot() (roll y luego pitch)
        v = p.intersect(fixed).val().Volume() + p.intersect(cr_w).val().Volume()
        worst = max(worst, v)
        print(f"  pose pitch {pit:+d} roll {rol:+d}: interferencia {v:.1f} mm3")
    asm = fixed.union(cr_w).union(cross.translate((0, 0, zoff + T.PLATE_T + Z_P))).union(
        plat.translate((0, 0, zoff + T.PLATE_T)))
    cq.exporters.export(asm, os.path.join(OUT, "neck3_assembly.stl"))
    print(f"altura de la plataforma sobre el suelo: {zoff + T.PLATE_T + Z_PL:.0f} mm; interferencia maxima {worst:.1f} mm3")


if __name__ == "__main__":
    main()
