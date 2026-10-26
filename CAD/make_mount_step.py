"""Mismo soporte de make_mount.py, pero como solidos B-rep (CadQuery) y exportado a STEP para FreeCAD.

    CAD/.venv/bin/python CAD/make_mount_step.py   ->  CAD/out/eye_mount.step, tray_test.step

Los parametros vienen de make_mount.py (un solo lugar para editarlos). Ejes, ver ese archivo.
"""
import os
import math
import cadquery as cq
import make_mount as p

OUT = p.OUT


def make_tray():
    """Bandeja en marco del modulo, centrada en el PCB."""
    w = p.PLATE_X[1] - p.PLATE_X[0]
    plate = (cq.Workplane("XY").box(w, 2 * p.PLATE_HALF_Y, p.PLATE_T, centered=False)
             .translate((p.PLATE_X[0], -p.PLATE_HALF_Y, p.PLATE_BOT)))
    pts = [(x, y) for x in p.HOLE_X for y in (-p.HOLE_Y, p.HOLE_Y)]
    bosses = (cq.Workplane("XY").workplane(offset=p.PLATE_TOP).pushPoints(pts)
              .circle(p.BOSS_D / 2).extrude(p.PCB_BOTTOM - p.PLATE_TOP))
    tray = plate.union(bosses)
    slot = (cq.Workplane("XY").box(p.SLOT_X[1] - p.SLOT_X[0], 2 * p.SLOT_HALF_Y, p.PLATE_T + 4, centered=False)
            .translate((p.SLOT_X[0], -p.SLOT_HALF_Y, p.PLATE_BOT - 2)))
    tray = tray.cut(slot)
    pilots = (cq.Workplane("XY").workplane(offset=p.PCB_BOTTOM).pushPoints(pts)
              .circle(p.PILOT_D / 2).extrude(-(p.STANDOFF_H + 0.5)))
    return tray.cut(pilots)


def place(shape, side):
    """Modulo -> montaje (misma cadena que make_mount.module_to_mount)."""
    yaw = (180.0 - p.INTERIOR_ANGLE) / 2.0 * side
    s = shape.translate((-p.PCB_CENTER_X, 0, 0))
    s = s.rotate((0, 0, 0), (0, 0, 1), -90)
    s = s.rotate((0, 0, 0), (0, 1, 0), yaw)
    return s.translate((side * p.EYE_SPACING / 2, 0, 0))


def bridge():
    """Prisma extruido en Y entre los bordes internos de las dos bandejas."""
    def mount_xz(side, zmod):
        # punto del borde interno (modulo y = +-PLATE_HALF_Y, x irrelevante en XZ) -> (X, Z) del montaje
        yaw = math.radians((180.0 - p.INTERIOR_ANGLE) / 2.0 * side)
        ym = p.PLATE_HALF_Y if side < 0 else -p.PLATE_HALF_Y  # borde interno de cada bandeja
        X0, Z0 = ym, zmod  # tras Rz(-90): X = y_modulo, Z = z_modulo
        X = X0 * math.cos(yaw) + Z0 * math.sin(yaw)
        Z = -X0 * math.sin(yaw) + Z0 * math.cos(yaw)
        return (X + side * p.EYE_SPACING / 2, Z)
    poly = [mount_xz(-1, p.PLATE_TOP), mount_xz(-1, p.PLATE_BOT),
            mount_xz(+1, p.PLATE_BOT), mount_xz(+1, p.PLATE_TOP)]
    y_top = -p.PLATE_X[0]       # mount Y = -x_modulo
    length = p.PLATE_X[1] - p.PLATE_X[0]
    # plano XZ: normal -Y, asi que se extruye desde Y=y_top hacia -Y
    return cq.Workplane("XZ", origin=(0, y_top, 0)).polyline(poly).close().extrude(length)


def main():
    os.makedirs(OUT, exist_ok=True)
    tray = make_tray()
    cq.exporters.export(tray, os.path.join(OUT, "tray_test.step"))
    mount = place(tray, -1).union(place(tray, +1)).union(bridge())
    ears = (cq.Workplane("XY").workplane(offset=-80).pushPoints([(0, -p.EAR_Y), (0, p.EAR_Y)])
            .circle(p.EAR_HOLE_D / 2).extrude(160))
    mount = mount.cut(ears).clean()
    cq.exporters.export(mount, os.path.join(OUT, "eye_mount.step"))
    s = mount.val()
    bb = s.BoundingBox()
    print("solidos:", len(mount.solids().vals()), "valido:", s.isValid(), "volumen mm3: %.0f" % s.Volume())
    print("bbox: %.1f x %.1f x %.1f" % (bb.xlen, bb.ylen, bb.zlen))


if __name__ == "__main__":
    main()
