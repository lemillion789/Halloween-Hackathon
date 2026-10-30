"""Soporte en L para poner vertical una PCB con 4 agujeros M3 en rectangulo HOLE_W x HOLE_H.

    CAD/.venv/Scripts/python CAD/make_pcb_stand.py  ->  CAD/out/pcb_stand.step, pcb_stand.stl

Ejes: X a lo largo de la PCB (HOLE_W horizontal), Z hacia arriba (piso en Z=0),
Y profundidad (PCB delante, en -Y; refuerzos y agujeros al piso detras, en +Y).
Imprimir de costado (perfil en L sobre la cama) para que la esquina no se separe entre capas.
"""
import os
import cadquery as cq

# --- parametros (mm) ---
HOLE_W = 64.0        # separacion horizontal entre agujeros
HOLE_H = 40.5        # separacion vertical entre agujeros
MARGIN = 6.0         # placa mas alla del centro de los agujeros
PLATE_T = 3.0        # grosor placa vertical
LIFT = 12.0          # altura del agujero inferior sobre la base (deja aire bajo la PCB)
STANDOFF_H = 6.0     # separacion PCB-placa (soldaduras de atras)
BOSS_D = 7.0
PILOT_D = 2.5        # 2.5 = M3 autorroscante en plastico; 3.2 = pasante con tuerca
BASE_T = 4.0
BASE_FRONT = 15.0    # base delante de la placa (bajo la PCB)
BASE_BACK = 40.0     # base detras de la placa
GUSSET = 25.0        # catetos del refuerzo triangular
GUSSET_T = 4.0
FLOOR_HOLE_D = 4.0   # agujeros para fijar al piso

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def make_stand():
    w = HOLE_W + 2 * MARGIN
    z_hole0 = BASE_T + LIFT
    h = z_hole0 + HOLE_H + MARGIN

    plate = cq.Workplane("XY").box(w, PLATE_T, h, centered=(True, False, False))
    base = (cq.Workplane("XY").box(w, BASE_FRONT + PLATE_T + BASE_BACK, BASE_T, centered=(True, False, False))
            .translate((0, -BASE_FRONT, 0)))
    stand = plate.union(base)

    # refuerzos triangulares detras, en los dos bordes
    for x in (-w / 2, w / 2 - GUSSET_T):
        tri = (cq.Workplane("YZ", origin=(x, 0, 0))
               .polyline([(PLATE_T, BASE_T), (PLATE_T + GUSSET, BASE_T), (PLATE_T, BASE_T + GUSSET)])
               .close().extrude(GUSSET_T))
        stand = stand.union(tri)

    # postes hacia delante (-Y) y agujeros piloto pasantes
    pts = [(x, z) for x in (-HOLE_W / 2, HOLE_W / 2) for z in (z_hole0, z_hole0 + HOLE_H)]
    bosses = cq.Workplane("XZ").pushPoints(pts).circle(BOSS_D / 2).extrude(STANDOFF_H)
    stand = stand.union(bosses)
    pilots = (cq.Workplane("XZ", origin=(0, PLATE_T + 1, 0)).pushPoints(pts)
              .circle(PILOT_D / 2).extrude(STANDOFF_H + PLATE_T + 2))
    stand = stand.cut(pilots)

    # agujeros al piso en la base trasera, entre los refuerzos
    y_fh = PLATE_T + BASE_BACK - 8
    fh = (cq.Workplane("XY").pushPoints([(-w / 4, y_fh), (w / 4, y_fh)])
          .circle(FLOOR_HOLE_D / 2).extrude(BASE_T))
    return stand.cut(fh)


def main():
    os.makedirs(OUT, exist_ok=True)
    s = make_stand()
    cq.exporters.export(s, os.path.join(OUT, "pcb_stand.step"))
    cq.exporters.export(s, os.path.join(OUT, "pcb_stand.stl"))
    bb = s.val().BoundingBox()
    print(f"OK  {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm  -> {OUT}")


if __name__ == "__main__":
    main()
