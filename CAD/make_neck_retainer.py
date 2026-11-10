"""Reten del cuello: evita que el neck se salga del horn del servo de giro.

Problema: el neck (soporte en U, MG996 kit) solo va unido a la base por el horn
del servo de giro; con peso, el vuelco arranca el horn del estriado.

Solucion (todo en coordenadas del ensamblaje `out/servo_assembly.stl`):
  1. neck_flanged : el neck original + una brida redonda (anillo) en su cara inferior.
  2. retainer_plate: plato fijo atornillado sobre las orejas del servo (con los
     tornillos de las orejas, mas largos, a los agujeros de los pilares) y con dos
     paredes que apoyan en el plato de la base. La brida gira justo encima.
  3. retainer_lip : anillo con labio que se atornilla al plato y atrapa la brida
     por arriba. Asi la base absorbe el peso y el vuelco y el servo solo hace girar.

Uso (venv de CAD):  .venv/Scripts/python make_neck_retainer.py   (Windows)
                    .venv/bin/python make_neck_retainer.py       (Linux)
Salida en out/: retainer_plate, retainer_lip (.step/.stl, orientados para imprimir),
neck_flanged.stl (orientado para imprimir) y retainer_assembly.stl (vista de conjunto).
"""
from pathlib import Path
import numpy as np
import trimesh
import cadquery as cq

HERE = Path(__file__).parent
OUT = HERE / "out"
ASSEMBLY = OUT / "servo_assembly.stl"

# ---- medidas tomadas del ensamblaje (mm, coordenadas del ensamblaje) ----
CX, CY = 165.55, 88.27        # eje del servo de giro (centro del horn)
BASE_X = (128.35, 182.35)     # huella de la base
BASE_Y = (61.12, 115.12)
BASE_TOP = 7.0                # cara superior del plato de la base
PILLAR_FILLET = 4.0           # chaflan a 45 grados al pie de los pilares
EAR_TOP = 40.1                # cara superior de las orejas del servo
SERVO_X = (135.05, 175.55)    # cuerpo del servo por encima de las orejas
SERVO_Y = (78.27, 98.27)
GUSSET_TOP = 42.0             # los nervios oreja-cuerpo llegan hasta aqui
NECK_BOTTOM = 49.7            # cara inferior del neck
EAR_HOLES = [(130.8, 83.1), (130.8, 93.1), (179.8, 83.1), (179.8, 93.1)]  # = agujeros de los pilares
PILLAR_Y = (76.1, 100.1)      # pilares en C de la base (en Y)

# ---- parametros del diseno ----
GAP_Z = 0.5          # holgura axial brida <-> plato / labio
GAP_R = 1.0          # holgura radial brida <-> pared del labio
SERVO_CLEAR = 0.6    # aire alrededor del cuerpo del servo
FLANGE_RI = 22.0     # brida del neck: radio interior (fuera del alojamiento del horn, R18.5)
FLANGE_RO = 45.0     # brida del neck: radio exterior
FLANGE_T = 4.0       # brida del neck: grosor
OUTER_R = 50.0       # radio exterior del plato y del labio
LIP_RI = 38.5        # radio interior del labio (el neck llega a R35.7)
LIP_T = 3.0          # grosor del labio
PLATE_Z0 = GUSSET_TOP + 0.4
PLATE_Z1 = NECK_BOTTOM - GAP_Z
WALL_GAP = 0.5       # aire entre paredes y pilares / borde de la base
BOSS_D = 5.0         # pastilla bajo el plato que aprieta cada oreja
EAR_SCREW_D = 2.9    # pasante para tornillo M2.5 (autorroscante en el agujero de 2 mm del pilar)
EAR_CB_D = 5.5       # avellanado/cajera de la cabeza
EAR_CB_FLOOR = 45.0  # suelo de la cajera (tornillo M2.5 x 16)
LIP_SCREWS = 6       # tornillos M3 labio -> plato
LIP_SCREW_R = (FLANGE_RO + GAP_R + OUTER_R) / 2
LIP_SCREW_D = 3.4
LIP_PILOT_D = 2.5    # autorroscante M3 en el plato
LIP_PILOT_DEPTH = 6.0


def cyl(r, z0, z1, x=CX, y=CY):
    return cq.Workplane("XY").workplane(offset=z0).center(x, y).circle(r).extrude(z1 - z0)


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def make_plate():
    plate = cyl(OUTER_R, PLATE_Z0, PLATE_Z1)
    # pastillas que bajan hasta las orejas
    for x, y in EAR_HOLES:
        plate = plate.union(cyl(BOSS_D / 2, EAR_TOP, PLATE_Z0 + 0.01, x, y))
    # paredes a los lados (Y) que apoyan en el plato de la base
    x0, x1 = BASE_X[0] + WALL_GAP, BASE_X[1] - WALL_GAP
    for y0, y1, inner, s in [(BASE_Y[0] + WALL_GAP, PILLAR_Y[0] - WALL_GAP, PILLAR_Y[0] - WALL_GAP, -1),
                             (PILLAR_Y[1] + WALL_GAP, BASE_Y[1] - WALL_GAP, PILLAR_Y[1] + WALL_GAP, 1)]:
        wall = box(x0, x1, y0, y1, BASE_TOP, PLATE_Z0 + 0.01)
        # chaflan a 45 grados en el pie interior: los pilares tienen un chaflan de 4 mm abajo
        c = PILLAR_FILLET + WALL_GAP + 0.5
        tri = (cq.Workplane("YZ").workplane(offset=x0 - 1)
               .polyline([(inner, BASE_TOP - 1), (inner + s * c + s * 1, BASE_TOP - 1), (inner, BASE_TOP + c + 1)]).close()
               .extrude(x1 - x0 + 2))
        plate = plate.union(wall.cut(tri))
    # hueco del cuerpo del servo
    plate = plate.cut(box(SERVO_X[0] - SERVO_CLEAR, SERVO_X[1] + SERVO_CLEAR,
                          SERVO_Y[0] - SERVO_CLEAR, SERVO_Y[1] + SERVO_CLEAR, EAR_TOP - 1, PLATE_Z1 + 1))
    # tornillos de las orejas: pasante + cajera desde arriba
    for x, y in EAR_HOLES:
        plate = plate.cut(cyl(EAR_SCREW_D / 2, EAR_TOP - 1, PLATE_Z1 + 1, x, y))
        plate = plate.cut(cyl(EAR_CB_D / 2, EAR_CB_FLOOR, PLATE_Z1 + 1, x, y))
    # agujeros piloto para los tornillos del labio
    for a in np.arange(LIP_SCREWS) * 2 * np.pi / LIP_SCREWS + np.pi / LIP_SCREWS:
        x, y = CX + LIP_SCREW_R * np.cos(a), CY + LIP_SCREW_R * np.sin(a)
        plate = plate.cut(cyl(LIP_PILOT_D / 2, PLATE_Z1 - LIP_PILOT_DEPTH, PLATE_Z1 + 1, x, y))
    return plate


def make_lip():
    wall_z1 = NECK_BOTTOM + FLANGE_T + GAP_Z
    lip = cyl(OUTER_R, PLATE_Z1, wall_z1 + LIP_T).cut(cyl(FLANGE_RO + GAP_R, PLATE_Z1 - 1, wall_z1))
    lip = lip.cut(cyl(LIP_RI, PLATE_Z1 - 1, wall_z1 + LIP_T + 1))
    for a in np.arange(LIP_SCREWS) * 2 * np.pi / LIP_SCREWS + np.pi / LIP_SCREWS:
        x, y = CX + LIP_SCREW_R * np.cos(a), CY + LIP_SCREW_R * np.sin(a)
        lip = lip.cut(cyl(LIP_SCREW_D / 2, PLATE_Z1 - 1, wall_z1 + LIP_T + 1, x, y))
    return lip


def to_mesh(wp, tol=0.05):
    path = OUT / "_tmp_retainer.stl"
    cq.exporters.export(wp, str(path), tolerance=tol, angularTolerance=0.1)
    m = trimesh.load(path)
    path.unlink()
    return m


def load_assembly():
    """Separa servo_assembly.stl: neck, servo, base, horn (por volumen) + tornillos."""
    parts = sorted(trimesh.load(ASSEMBLY).split(only_watertight=False), key=lambda p: -abs(p.volume))
    neck, servo, base, horn = parts[:4]
    assert abs(base.extents[2] - 37.6) < 0.5 and abs(neck.extents[2] - 50.0) < 0.5, "orden de piezas inesperado"
    return neck, servo, base, horn, parts[4:]


def flip_for_print(m):
    """Gira 180 grados en X (cara superior sobre la cama) y apoya en z=0."""
    m = m.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0], [CX, CY, 0]))
    m.apply_translation([-CX, -CY, -m.bounds[0][2]])
    return m


def main():
    neck, servo, base, horn, screws = load_assembly()
    plate, lip = make_plate(), make_lip()
    flange = cyl(FLANGE_RO, NECK_BOTTOM, NECK_BOTTOM + FLANGE_T).cut(cyl(FLANGE_RI, NECK_BOTTOM - 1, NECK_BOTTOM + FLANGE_T + 1))
    plate_m, lip_m, flange_m = to_mesh(plate), to_mesh(lip), to_mesh(flange)
    neck_f = trimesh.boolean.union([neck, flange_m], engine="manifold")

    # STEP del plato y del labio (orientados para imprimir: cara superior abajo)
    flip = lambda wp: wp.rotate((CX, CY, 0), (CX + 1, CY, 0), 180)
    for name, wp, m in [("retainer_plate", plate, plate_m), ("retainer_lip", lip, lip_m)]:
        f = flip(wp)
        z0 = f.val().BoundingBox().zmin
        cq.exporters.export(f.translate((-CX, -CY, -z0)), str(OUT / f"{name}.step"))
        flip_for_print(m).export(OUT / f"{name}.stl")
    nf = neck_f.copy(); nf.apply_translation([-CX, -CY, -nf.bounds[0][2]])
    nf.export(OUT / "neck_flanged.stl")
    trimesh.util.concatenate([base, servo, horn, neck_f, plate_m, lip_m] + screws).export(OUT / "retainer_assembly.stl")

    # chequeo de choques: piezas fijas contra fijas, y el neck girado contra lo fijo
    def inter(a, b):
        try:
            return abs(trimesh.boolean.intersection([a, b], engine="manifold").volume)
        except Exception:
            return 0.0
    print("volumen de choque (mm3, deberia ser ~0):")
    for n, a in [("plato", plate_m), ("labio", lip_m)]:
        for m_n, b in [("base", base), ("servo", servo), ("horn", horn)]:
            print(f"  {n:6s} x {m_n:6s}: {inter(a, b):8.2f}")
    print(f"  plato  x labio : {inter(plate_m, lip_m):8.2f}")
    for ang in range(-90, 91, 15):
        r = neck_f.copy()
        r.apply_transform(trimesh.transformations.rotation_matrix(np.radians(ang), [0, 0, 1], [CX, CY, 0]))
        print(f"  neck {ang:+4d} deg: plato {inter(r, plate_m):6.2f}  labio {inter(r, lip_m):6.2f}  servo {inter(r, servo):6.2f}")
    print("listo:", ", ".join(f"{n}" for n in ["retainer_plate.step/.stl", "retainer_lip.step/.stl",
                                                 "neck_flanged.stl", "retainer_assembly.stl"]))


if __name__ == "__main__":
    main()
