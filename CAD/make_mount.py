"""Soporte para 2 pantallas TFT 1.8" ST7735 (ojos), pines arriba, verticales, en V.

Uso (desde la raiz del proyecto):
    CAD/.venv/bin/python CAD/make_mount.py

Genera en CAD/out/:
    eye_mount.stl         soporte completo (2 bandejas + puente)
    tray_test.stl         una sola bandeja plana, para probar el encaje antes de imprimir todo
    assembly_preview.stl  soporte + las 2 pantallas (solo para ver, NO imprimir)

Marco del modulo (del STL de FluSneez): x = largo (pines en x<0), y = ancho, z = hacia el frente
(PCB entre z=-1.6 y 0, vidrio hasta z=2.8, componentes traseros hasta z=-4.2, pines hasta z=-10).
Marco del montaje: X derecha, Y arriba, Z hacia el frente (quien mira los ojos).
"""
import os
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
TFT_STL = os.path.join(HERE, "1.8 TFT Display ST7735 - 3898101", "files", "LCD_TFT_1.8_v3.stl")

# ---------------- parametros ----------------
INTERIOR_ANGLE = 130.0   # angulo entre los planos de las dos pantallas, medido por detras (V hacia el frente)
EYE_SPACING = 64.0       # distancia entre centros de pantallas (mm); ajustar a las cuencas
STANDOFF_H = 4.0         # separacion PCB-bandeja (componentes traseros llegan a 2.6 mm bajo el PCB)
PLATE_T = 3.0            # grosor de la bandeja
BOSS_D = 6.5             # diametro exterior de los postes
PILOT_D = 2.5            # agujero guia (M3 autorroscante; usar 3.2 si van con tuerca / 2.2 para M2.5)
HOLE_Y = 14.3            # los 4 agujeros del PCB estan en y=+-14.3
HOLE_X = (-26.7, 25.3)   # x de los agujeros (lado pines, lado opuesto)
PLATE_X = (-31.0, 29.5)  # extension de la bandeja en x del modulo
PLATE_HALF_Y = 18.5
SLOT_X = (-32.0, -24.2)  # ranura para el cabezal de pines (sale hacia atras)
SLOT_HALF_Y = 10.6
EAR_HOLE_D = 3.4         # agujeros de fijacion del puente a la calavera (en X=0)
EAR_Y = 20.0
PCB_CENTER_X = -0.625    # centro del PCB en x del modulo

PCB_BOTTOM = -1.6
PLATE_TOP = PCB_BOTTOM - STANDOFF_H
PLATE_BOT = PLATE_TOP - PLATE_T


def box(x0, x1, y0, y1, z0, z1):
    b = trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
    b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    return b


def cyl(x, y, z0, z1, d, sections=48):
    c = trimesh.creation.cylinder(radius=d / 2, height=z1 - z0, sections=sections)
    c.apply_translation([x, y, (z0 + z1) / 2])
    return c


def union(parts):
    return trimesh.boolean.union(parts, engine="manifold")


def diff(a, b):
    return trimesh.boolean.difference([a, b], engine="manifold")


def make_tray():
    """Bandeja en marco del modulo, centrada en el PCB."""
    plate = box(PLATE_X[0], PLATE_X[1], -PLATE_HALF_Y, PLATE_HALF_Y, PLATE_BOT, PLATE_TOP)
    bosses = [cyl(x, y, PLATE_TOP - 0.01, PCB_BOTTOM, BOSS_D)
              for x in HOLE_X for y in (-HOLE_Y, HOLE_Y)]
    tray = union([plate] + bosses)
    tray = diff(tray, box(SLOT_X[0], SLOT_X[1], -SLOT_HALF_Y, SLOT_HALF_Y, PLATE_BOT - 1, PLATE_TOP + 1))
    for x in HOLE_X:
        for y in (-HOLE_Y, HOLE_Y):
            tray = diff(tray, cyl(x, y, PLATE_TOP + 0.5, PCB_BOTTOM + 0.1, PILOT_D, 24))
    return tray


def module_to_mount(side):
    """Matriz 4x4 modulo -> montaje para la pantalla izquierda (-1) o derecha (+1)."""
    yaw = np.radians((180.0 - INTERIOR_ANGLE) / 2.0) * side  # normal apunta hacia afuera
    rz = trimesh.transformations.rotation_matrix(np.radians(-90), [0, 0, 1])  # pines arriba
    ry = trimesh.transformations.rotation_matrix(yaw, [0, 1, 0])
    center = trimesh.transformations.translation_matrix([-PCB_CENTER_X, 0, 0])
    place = trimesh.transformations.translation_matrix([side * EYE_SPACING / 2, 0, 0])
    return place @ ry @ rz @ center


def bridge(tm_left, tm_right):
    """Casco convexo entre los bordes internos de las dos bandejas."""
    pts = []
    for tm, y in ((tm_left, PLATE_HALF_Y), (tm_right, -PLATE_HALF_Y)):
        for x in PLATE_X:
            for z in (PLATE_BOT, PLATE_TOP):
                p = tm @ np.array([x, y, z, 1.0])
                pts.append(p[:3])
    return trimesh.convex.convex_hull(np.array(pts))


def main():
    os.makedirs(OUT, exist_ok=True)
    tray = make_tray()
    tray.export(os.path.join(OUT, "tray_test.stl"))

    tl, tr = module_to_mount(-1), module_to_mount(+1)
    left, right = tray.copy(), tray.copy()
    left.apply_transform(tl)
    right.apply_transform(tr)
    br = bridge(tl, tr)
    mount = union([left, right, br])
    for y in (-EAR_Y, EAR_Y):
        mount = diff(mount, cyl(0, y, -80, 80, EAR_HOLE_D, 32).copy())
    # el cilindro es vertical en Z (perpendicular al puente): atraviesa el puente de frente a atras
    mount.export(os.path.join(OUT, "eye_mount.stl"))

    tft = trimesh.load(TFT_STL)
    pl, pr = tft.copy(), tft.copy()
    pl.apply_transform(tl)
    pr.apply_transform(tr)
    trimesh.util.concatenate([mount, pl, pr]).export(os.path.join(OUT, "assembly_preview.stl"))

    print("watertight:", mount.is_watertight, "volumen mm3: %.0f" % mount.volume)
    print("tamano (mm):", np.round(mount.extents, 1))


if __name__ == "__main__":
    main()
