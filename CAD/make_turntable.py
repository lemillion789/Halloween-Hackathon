"""Base giratoria para la calavera con servo MG996R (eje vertical, apuntando hacia arriba).

    CAD/.venv/Scripts/python CAD/make_turntable.py
    ->  CAD/out/turntable_base.step/.stl, turntable_top.step/.stl, turntable_assembly.stl

Dos piezas:
  - turntable_base: disco de apoyo + alojamiento del servo (cuelga de sus orejas) + anillo guia
    exterior cuya cara superior queda GUIDE_GAP por debajo del plato (ahi va la guia/rodamiento).
  - turntable_top: plato que se atornilla al horn redondo del servo, con cuna en trapecio
    para la cabeza (HEAD_L, HEAD_W_LONG, HEAD_W_SHORT) y agujeros para pasar los cables de los ojos.
Ejes: Z hacia arriba (piso en Z=0), eje del servo en X=Y=0, cuerpo del servo a lo largo de X.
Cotas del MG996R tomadas de la hoja tipica: MEDIR el servo real (sobre todo FLANGE_Z y el horn).
Imprimir ambas piezas tal cual salen (base con el disco sobre la cama, plato con la cuna hacia arriba).
"""
import os
import cadquery as cq

# --- servo MG996R (mm) ---
SERVO_L = 40.7       # largo del cuerpo (X)
SERVO_W = 19.7       # ancho del cuerpo (Y)
SERVO_H = 42.9       # fondo del cuerpo -> punta del eje
SHAFT_FROM_END = 10.2  # centro del eje -> extremo cercano del cuerpo
FLANGE_Z = 28.0      # fondo del cuerpo -> cara inferior de las orejas
FLANGE_L = 54.5      # largo total con orejas
EAR_HOLE_DX = 49.5   # separacion de agujeros a lo largo
EAR_HOLE_DY = 10.0   # separacion de agujeros a lo ancho
EAR_SCREW_D = 3.4    # tornillo M3 (pasa por el agujero de la oreja y por la ranura) + tuerca atrapada
EAR_SLOT_TOL = 1.5   # las ranuras permiten +-1.5 mm de error en la separacion de agujeros (a lo largo)
NUT_AF = 5.9         # tuerca M3 entre caras (5.5) + holgura
NUT_T = 2.7          # grosor de la tuerca M3 (2.4) + holgura
NUT_DEPTH = 2.0      # piel de plastico entre la oreja y la tuerca
FIT = 0.5            # holgura por lado del hueco del servo

# --- horn redondo (el disco que trae el servo) ---
HORN_D = 25.0        # diametro del disco
HORN_TOP = 2.5       # cuanto sobresale la cara del horn sobre la punta del eje
HORN_HOLES_R = 9.5   # radio de los agujeros del horn que se usan (medido)
HORN_HOLE_D = 1.8    # pasante para los tornillos M1.5 del horn
HEAD_SCREW_D = 6.0   # arandela de 5.5 + holgura; avellanado para que las cabezas queden a ras del plato
HEAD_SCREW_DEPTH = 1.5
HORN_SCREW_ACCESS = 7.0  # agujero central para meter el destornillador del tornillo del eje

# --- base ---
FOOT_D = 110.0
FOOT_T = 3.0
FOOT_HOLE_D = 4.5
FOOT_HOLE_R = 50.0
BODY_CLEAR = 1.0     # aire bajo el fondo del servo (cuelga de las orejas)
WALL = 2.5           # pared del alojamiento
GUIDE_OD = 90.0      # anillo guia exterior
GUIDE_T = 2.5
GUIDE_GAP = 1.0      # aire entre anillo y plato; si pones rodamiento/lazy susan, sube a su grosor
CABLE_W = 12.0       # ranura para el cable del servo (sale por el extremo lejano al eje)
CABLE_H = 10.0

# --- plato y cabeza ---
HEAD_L = 140.0       # largo de la base de la calavera (frente-nuca), en X
HEAD_W_LONG = 105.0  # base en trapecio simetrico: lado largo (en -X)
HEAD_W_SHORT = 55.0  # lado corto (en +X)
HEAD_FIT = 1.5       # holgura por lado en la cuna
PLATE_R = 48.0       # disco bajo la cuna que tapa el anillo guia en todo el giro
PLATE_T = 3.0
LIP_H = 5.0          # altura del borde de la cuna
LIP_T = 2.0
WIRE_HOLE_D = 12.0   # pasacables para los ojos (dos, a los lados del eje)
WIRE_HOLE_X = 30.0

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# alturas derivadas
Z_BODY = FOOT_T + BODY_CLEAR                 # fondo del servo
Z_FLANGE = Z_BODY + FLANGE_Z                 # cara inferior de las orejas = tope del alojamiento
Z_PLATE = Z_BODY + SERVO_H + HORN_TOP       # cara inferior del plato = cara del horn
Z_GUIDE = Z_PLATE - GUIDE_GAP
BODY_CX = -(SERVO_L / 2 - SHAFT_FROM_END)   # centro del cuerpo (el eje queda en X=0)


def make_base():
    foot = cq.Workplane("XY").circle(FOOT_D / 2).extrude(FOOT_T)
    holes = (cq.Workplane("XY").polarArray(FOOT_HOLE_R, 45, 360, 4)
             .circle(FOOT_HOLE_D / 2).extrude(FOOT_T))
    foot = foot.cut(holes)

    # alojamiento: bloque bajo las orejas con hueco para el cuerpo
    blk_l = FLANGE_L + 2 * WALL
    blk_w = SERVO_W + 2 * FIT + 2 * WALL
    block = (cq.Workplane("XY").box(blk_l, blk_w, Z_FLANGE - FOOT_T, centered=(True, True, False))
             .translate((BODY_CX, 0, FOOT_T)))
    pocket = (cq.Workplane("XY").box(SERVO_L + 2 * FIT, SERVO_W + 2 * FIT, Z_FLANGE, centered=(True, True, False))
              .translate((BODY_CX, 0, FOOT_T)))
    ears = [(BODY_CX + sx * EAR_HOLE_DX / 2, sy * EAR_HOLE_DY / 2) for sx in (-1, 1) for sy in (-1, 1)]
    # ranuras pasantes (tornillo M3) + ranura lateral para deslizar la tuerca desde el extremo del bloque
    pilots = None
    for (ex, ey) in ears:
        sx = 1 if ex > BODY_CX else -1
        slot = (cq.Workplane("XY").box(EAR_SCREW_D + 2 * EAR_SLOT_TOL, EAR_SCREW_D, 15, centered=(True, True, False))
                .translate((ex, ey, Z_FLANGE - 15)))
        x_in = ex - sx * (NUT_AF / 2 + EAR_SLOT_TOL)
        x_out = BODY_CX + sx * (blk_l / 2 + 1)
        nut = (cq.Workplane("XY").box(abs(x_out - x_in), NUT_AF, NUT_T, centered=False)
               .translate((min(x_in, x_out), ey - NUT_AF / 2, Z_FLANGE - NUT_DEPTH - NUT_T)))
        pilots = slot.union(nut) if pilots is None else pilots.union(slot).union(nut)

    # anillo guia exterior
    ring = (cq.Workplane("XY").circle(GUIDE_OD / 2).circle(GUIDE_OD / 2 - GUIDE_T)
            .extrude(Z_GUIDE - FOOT_T).translate((0, 0, FOOT_T)))

    base = foot.union(block).union(ring).cut(pocket).cut(pilots)

    # ranura del cable: desde el hueco del servo hacia -X, atravesando bloque y anillo
    x_end = BODY_CX - SERVO_L / 2
    slot = (cq.Workplane("XY").box(GUIDE_OD / 2 + x_end + 5, CABLE_W, CABLE_H, centered=False)
            .translate((-GUIDE_OD / 2 - 5, -CABLE_W / 2, FOOT_T)))
    return base.cut(slot)


def head_prism(off, h_z):
    """Prisma de alto h_z con el trapecio de la base de la cabeza crecido 'off' mm (esquinas redondeadas).
    El centroide queda sobre el eje para que el peso no cargue de lado el servo."""
    l, s, h = HEAD_W_LONG, HEAD_W_SHORT, HEAD_L
    x_long = -h * (l + 2 * s) / (3 * (l + s))
    pts = [(x_long, -l / 2), (x_long + h, -s / 2), (x_long + h, s / 2), (x_long, l / 2)]
    w = cq.Workplane("XY").polyline(pts).close()
    return (w.offset2D(off, "arc") if off else w).extrude(h_z)


def make_top():
    outer = HEAD_FIT + LIP_T
    plate = head_prism(outer, PLATE_T).union(cq.Workplane("XY").circle(PLATE_R).extrude(PLATE_T))
    lip = head_prism(outer, LIP_H).cut(head_prism(HEAD_FIT, LIP_H)).translate((0, 0, PLATE_T))
    top = plate.union(lip)

    access = cq.Workplane("XY").circle(HORN_SCREW_ACCESS / 2).extrude(PLATE_T)
    horn_holes = (cq.Workplane("XY").polarArray(HORN_HOLES_R, 0, 360, 4)
                  .circle(HORN_HOLE_D / 2).extrude(PLATE_T))
    heads = (cq.Workplane("XY", origin=(0, 0, PLATE_T - HEAD_SCREW_DEPTH)).polarArray(HORN_HOLES_R, 0, 360, 4)
             .circle(HEAD_SCREW_D / 2).extrude(HEAD_SCREW_DEPTH))
    wires = (cq.Workplane("XY").pushPoints([(-WIRE_HOLE_X, 0), (WIRE_HOLE_X, 0)])
             .circle(WIRE_HOLE_D / 2).extrude(PLATE_T))
    return top.cut(access).cut(horn_holes).cut(heads).cut(wires)


def make_servo_dummy():
    body = (cq.Workplane("XY").box(SERVO_L, SERVO_W, SERVO_H - 6, centered=(True, True, False))
            .translate((BODY_CX, 0, Z_BODY)))
    ears = (cq.Workplane("XY").box(FLANGE_L, SERVO_W, 2.5, centered=(True, True, False))
            .translate((BODY_CX, 0, Z_FLANGE)))
    shaft = cq.Workplane("XY").circle(3).extrude(6).translate((0, 0, Z_BODY + SERVO_H - 6))
    horn = cq.Workplane("XY").circle(HORN_D / 2).extrude(HORN_TOP).translate((0, 0, Z_BODY + SERVO_H))
    return body.union(ears).union(shaft).union(horn)


def main():
    os.makedirs(OUT, exist_ok=True)
    base, top = make_base(), make_top()
    for name, part in (("turntable_base", base), ("turntable_top", top)):
        cq.exporters.export(part, os.path.join(OUT, name + ".step"))
        cq.exporters.export(part, os.path.join(OUT, name + ".stl"))
        bb = part.val().BoundingBox()
        print(f"{name}: {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm")
    asm = base.union(make_servo_dummy()).union(top.translate((0, 0, Z_PLATE)))
    cq.exporters.export(asm, os.path.join(OUT, "turntable_assembly.stl"))
    print(f"plato en Z={Z_PLATE:.1f}, anillo guia hasta Z={Z_GUIDE:.1f}, orejas en Z={Z_FLANGE:.1f}  -> {OUT}")


if __name__ == "__main__":
    main()
