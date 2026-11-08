"""Cuello de 2 ejes (giro + cabeceo) para la calavera con 2 servos MG995/MG996R.

    CAD/.venv/bin/python CAD/make_neck.py            -> piezas + vista de montaje + chequeo de choques
    CAD/.venv/bin/python CAD/make_neck.py --fit-test -> solo la pieza de prueba del servo (imprimir primero, ~15 min)

Mecanismo (el clasico pan/tilt apilado, como en los cuellos de animatronicos):
  - GIRO: servo vertical en turntable_base (make_turntable.py), el horn redondo mueve neck_pan_top.
  - CABECEO: neck_pan_top lleva una pared con el servo de cabeceo (eje horizontal, a lo largo de Y)
    y, enfrente, un poste con un perno M5 como pivote (el perno soporta el peso, el servo solo gira).
    neck_cradle cuelga de ambos (horn en un lado, perno en el otro) y lleva la cuna de la cabeza.
  - Eje del cabeceo sobre el eje del giro y cabeza centrada sobre ambos: sin par de peso en reposo.
Recorrido de cabeceo +-30 grados (firmware: TILT_MIN 60 .. TILT_MAX 120).

Ejes: Z arriba, eje de giro en X=Y=0, eje de cabeceo = linea Y en X=0, Z=Z_AX sobre el plato.
Tornilleria: orejas del servo con M3 + tuerca (ranuras +-1.5 mm por si el MG995 difiere); horn: tornillos
del servo; pivote: perno M5 x ~40 con tuerca autofrenante y arandelas.
Montaje: 1) plato al horn del servo de giro, 2) servo de cabeceo por fuera (cuerpo hacia dentro) con sus M3,
3) horn en el servo, 4) brazo del cuna al horn, 5) perno M5 por el otro brazo y el poste.
"""
import os
import sys
import cadquery as cq
import make_turntable as T

OUT = T.OUT

# --- cabeceo ---
WT = 6.0            # grosor de la pared del servo y del poste del pivote
YW = 22.0           # cara exterior de la pared/poste (|Y|)
Z_AX = T.SERVO_W / 2 + T.FIT + 3.5   # eje de cabeceo sobre el plato (3.5 mm de suelo bajo el servo)
WALL_TOP = Z_AX + 14.0
ARM_T = 4.0
HUB_R = 13.0        # cubo del brazo alrededor del eje (no baja del plato al inclinar)
ARM_W = 26.0        # ancho del alma del brazo (X)
CRADLE_UNDER = Z_AX + 40.0   # cara inferior de la cuna: libra la pared al inclinar +-30 grados
PIVOT_D = 5.4       # perno M5
BOSS_D = 14.0
SLOT_W = T.EAR_SCREW_D + 2 * T.EAR_SLOT_TOL

# y del horn: cara del horn = pared + (punta del eje sobre la oreja) + HORN_TOP
Y_ARM_IN = YW + (T.SERVO_H - T.FLANGE_Z) + T.HORN_TOP
BODY_CX = T.BODY_CX


def ear_holes_xz():
    return [(BODY_CX + sx * T.EAR_HOLE_DX / 2, Z_AX + sz * T.EAR_HOLE_DY / 2) for sx in (-1, 1) for sz in (-1, 1)]


def servo_wall(y_out, sign=1):
    """Pared en XZ con el hueco del servo, 4 ranuras M3 y ranuras laterales para tuercas.
    y_out = cara exterior (|Y|); la pared ocupa de y_out-WT a y_out (hacia el centro)."""
    wl = T.FLANGE_L + 2 * T.WALL + 4
    wall = (cq.Workplane("XY").box(wl, WT, WALL_TOP, centered=(True, True, False))
            .translate((BODY_CX, y_out - WT / 2, 0)))
    opening = (cq.Workplane("XY").box(T.SERVO_L + 2 * T.FIT, WT + 2, T.SERVO_W + 2 * T.FIT, centered=True)
               .translate((BODY_CX, y_out - WT / 2, Z_AX)))
    wall = wall.cut(opening)
    for (ex, ez) in ear_holes_xz():
        sx = 1 if ex > BODY_CX else -1
        slot = (cq.Workplane("XY").box(SLOT_W, WT + 2, T.EAR_SCREW_D, centered=True)
                .translate((ex, y_out - WT / 2, ez)))
        x_in = ex - sx * (T.NUT_AF / 2 + T.EAR_SLOT_TOL)
        x_out = BODY_CX + sx * (wl / 2 + 1)
        nut = (cq.Workplane("XY").box(abs(x_out - x_in), T.NUT_T, T.NUT_AF, centered=False)
               .translate((min(x_in, x_out), y_out - T.NUT_DEPTH - T.NUT_T, ez - T.NUT_AF / 2)))
        wall = wall.cut(slot).cut(nut)
    return wall


def make_pan_top():
    """Plato del giro (Z=0 cara inferior sobre el horn) + pared del servo de cabeceo + poste del pivote."""
    pt = T.PLATE_T
    plate = cq.Workplane("XY").circle(T.PLATE_R).extrude(pt)
    # (tapa el anillo guia de la base en todo el giro, igual que turntable_top)
    access = cq.Workplane("XY").circle(T.HORN_SCREW_ACCESS / 2).extrude(pt)
    horn_holes = (cq.Workplane("XY").polarArray(T.HORN_HOLES_R, 0, 360, 4).circle(T.HORN_HOLE_D / 2).extrude(pt))
    heads = (cq.Workplane("XY", origin=(0, 0, pt - T.HEAD_SCREW_DEPTH)).polarArray(T.HORN_HOLES_R, 0, 360, 4)
             .circle(T.HEAD_SCREW_D / 2).extrude(T.HEAD_SCREW_DEPTH))
    plate = plate.cut(access).cut(horn_holes).cut(heads)

    # pared del servo (Y+) y poste del pivote (Y-)
    wall = servo_wall(YW).translate((0, 0, pt))
    post = (cq.Workplane("XY").box(34, WT, WALL_TOP, centered=(True, True, False))
            .translate((0, -(YW - WT / 2), pt)))
    boss = (cq.Workplane("XZ", origin=(0, -YW, pt + Z_AX)).circle(BOSS_D / 2)
            .extrude(Y_ARM_IN - YW - 1.0))     # sobresale hacia -Y hasta 1 mm del brazo
    post = post.union(boss)
    # nervios triangulares (en YZ) para que no se doblen
    ribs = None
    for x in (BODY_CX - 33.5, BODY_CX + 31.5, -15.0, 13.0):
        sgn = 1 if x in (BODY_CX - 33.5, BODY_CX + 31.5) else -1
        y0 = sgn * (YW - WT)
        y1 = sgn * (YW - WT - 14)
        tri = (cq.Workplane("YZ", origin=(x, 0, pt)).polyline([(y0, 0), (y1, 0), (y0, WALL_TOP - 6)]).close().extrude(2.0))
        ribs = tri if ribs is None else ribs.union(tri)
    top = plate.union(wall).union(post).union(ribs)
    # cables de los ojos hacia abajo (a +X, fuera del servo y de la pared)
    wires = (cq.Workplane("XY").pushPoints([(32, -12), (32, 12)]).circle(T.WIRE_HOLE_D / 2 - 1).extrude(pt))
    top = top.cut(wires)
    # agujero del pivote (perno M5) atraviesa poste y boss
    pivot = (cq.Workplane("XZ", origin=(0, -YW + WT, pt + Z_AX)).circle(PIVOT_D / 2).extrude(Y_ARM_IN - YW + WT))
    return top.cut(pivot)


def arm(y_face, sign, servo_side):
    """Brazo en XZ: cubo alrededor del eje + alma hasta la cuna. y_face = cara que toca el horn / el boss (|Y|)."""
    y0 = sign * y_face
    y1 = sign * (y_face + ARM_T)
    wp = cq.Workplane("XZ", origin=(0, max(y0, y1), Z_AX))   # normal -Y: extruye hacia -Y
    hub = wp.circle(HUB_R).extrude(ARM_T)
    web = (cq.Workplane("XZ", origin=(0, max(y0, y1), Z_AX)).center(0, (CRADLE_UNDER + 1 - Z_AX) / 2)
           .rect(ARM_W, CRADLE_UNDER + 1 - Z_AX).extrude(ARM_T))
    a = hub.union(web)
    if servo_side:
        a = a.cut(cq.Workplane("XZ", origin=(0, max(y0, y1), Z_AX)).circle(T.HORN_SCREW_ACCESS / 2).extrude(ARM_T))
        for ang in (0, 90, 180, 270):
            import math
            px, pz = T.HORN_HOLES_R * math.cos(math.radians(ang)), T.HORN_HOLES_R * math.sin(math.radians(ang))
            a = a.cut(cq.Workplane("XZ", origin=(px, max(y0, y1), Z_AX + pz)).circle(T.HORN_HOLE_D / 2).extrude(ARM_T))
            # avellanado en la cara exterior (y_face + ARM_T)
            ysrc = sign * (y_face + ARM_T)
            a = a.cut(cq.Workplane("XZ", origin=(px, ysrc if sign < 0 else ysrc, Z_AX + pz))
                      .circle(T.HEAD_SCREW_D / 2).extrude(T.HEAD_SCREW_DEPTH * (1 if sign > 0 else -1)))
    else:
        a = a.cut(cq.Workplane("XZ", origin=(0, max(y0, y1), Z_AX)).circle(PIVOT_D / 2).extrude(ARM_T))
    return a


def make_cradle():
    """Cuna de la cabeza + dos brazos. Imprimir BOCA ABAJO (cuna sobre la cama, brazos hacia arriba)."""
    outer = T.HEAD_FIT + T.LIP_T
    plate = T.head_prism(outer, T.PLATE_T).translate((0, 0, CRADLE_UNDER))
    tab = (cq.Workplane("XY").box(ARM_W + 6, 2 * (Y_ARM_IN + ARM_T) + 4, T.PLATE_T, centered=(True, True, False))
           .translate((0, 0, CRADLE_UNDER)))
    lip = (T.head_prism(outer, T.LIP_H).cut(T.head_prism(T.HEAD_FIT, T.LIP_H))
           .translate((0, 0, CRADLE_UNDER + T.PLATE_T)))
    c = plate.union(tab).union(lip)
    c = c.union(arm(Y_ARM_IN, +1, True)).union(arm(Y_ARM_IN, -1, False))
    # los brazos entran hasta la cara inferior de la cuna: se eliminan las partes que sobresalen del plato por arriba
    wires = (cq.Workplane("XY", origin=(0, 0, CRADLE_UNDER)).pushPoints([(-30, 0), (30, 0)])
             .circle(T.WIRE_HOLE_D / 2).extrude(T.PLATE_T))
    return c.cut(wires)


def make_dummy_servo():
    """Servo de cabeceo (eje a lo largo de +Y) para la vista de montaje."""
    body = (cq.Workplane("XY").box(T.SERVO_L, T.SERVO_H - 6, T.SERVO_W, centered=(True, False, True))
            .translate((BODY_CX, YW - T.FLANGE_Z, Z_AX)))
    ears = (cq.Workplane("XY").box(T.FLANGE_L, 2.5, T.SERVO_W, centered=(True, False, True))
            .translate((BODY_CX, YW, Z_AX)))
    shaft = (cq.Workplane("XZ", origin=(0, YW - T.FLANGE_Z + T.SERVO_H, Z_AX)).circle(3).extrude(6))
    horn = (cq.Workplane("XZ", origin=(0, YW - T.FLANGE_Z + T.SERVO_H + T.HORN_TOP, Z_AX)).circle(T.HORN_D / 2)
            .extrude(T.HORN_TOP))
    return body.union(ears).union(shaft).union(horn)


def make_fit_test():
    """Trozo de pared con el hueco y las 4 ranuras para probar el servo antes de imprimir todo."""
    w = servo_wall(WT)
    fl = T.FLANGE_L + 2 * T.WALL + 4
    # recortar a la altura de las orejas para imprimir rapido
    w = w.intersect(cq.Workplane("XY").box(fl + 2, WT + 2, 2 * Z_AX + 12, centered=(True, True, False))
                    .translate((BODY_CX, WT / 2, 0)))
    return w


def export(name, part):
    cq.exporters.export(part, os.path.join(OUT, name + ".step"))
    cq.exporters.export(part, os.path.join(OUT, name + ".stl"))
    bb = part.val().BoundingBox()
    print(f"{name}: {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm")


def main():
    os.makedirs(OUT, exist_ok=True)
    if "--fit-test" in sys.argv:
        export("servo_fit_test", make_fit_test())
        return
    base = T.make_base()
    pan_top = make_pan_top()
    cradle = make_cradle()
    export("turntable_base", base)
    export("neck_pan_top", pan_top)
    export("neck_cradle", cradle)
    export("servo_fit_test", make_fit_test())

    # montaje y chequeo de choques con la cuna inclinada
    import math
    pan_servo = T.make_servo_dummy()
    pan_world = pan_top.translate((0, 0, T.Z_PLATE))
    tilt_servo = make_dummy_servo().translate((0, 0, T.Z_PLATE + T.PLATE_T))
    worst = 0.0
    for ang in (-30, -15, 0, 15, 30):
        c = (cradle.translate((0, 0, -Z_AX)).rotate((0, 0, 0), (0, 1, 0), ang)
             .translate((0, 0, Z_AX + T.Z_PLATE + T.PLATE_T)))
        hit = c.intersect(pan_world).val().Volume() + c.intersect(tilt_servo).val().Volume() \
            + c.intersect(base).val().Volume()
        worst = max(worst, hit)
        print(f"  cabeceo {ang:+d} deg: interferencia {hit:.2f} mm3")
    asm = base.union(pan_servo).union(pan_world).union(tilt_servo).union(
        cradle.translate((0, 0, T.Z_PLATE + T.PLATE_T)))
    cq.exporters.export(asm, os.path.join(OUT, "neck_assembly.stl"))
    print(f"Z_AX={Z_AX:.1f} sobre el plato; altura total hasta la cuna = {T.Z_PLATE + T.PLATE_T + CRADLE_UNDER:.0f} mm; "
          f"interferencia maxima {worst:.2f} mm3")


if __name__ == "__main__":
    main()
