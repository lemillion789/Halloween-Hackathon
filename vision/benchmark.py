"""Compara modelos sobre test_images/: acierto (etiqueta del nombre de archivo) y latencia.

Uso: .venv/Scripts/python benchmark.py meta/llama-3.2-90b-vision-instruct qwen3-vl:2b-instruct
Guarda los resultados en results_<modelo>.json
"""
import json
import pathlib
import sys

import cv2

from costume_describer import describe

HERE = pathlib.Path(__file__).parent
IMAGES = [p for p in sorted((HERE / "test_images").glob("*.jpg")) if p.read_bytes()[:2] == b"\xff\xd8"]

# sinonimos aceptados para cada etiqueta esperada
ALIASES = {
    "spider-man": ["spider"],
    "darth_vader": ["vader"],
    "harley_quinn": ["harley"],
    "wonder_woman": ["wonder woman"],
    "zombie": ["zombie", "undead"],
    "skeleton": ["skeleton", "skull", "calavera", "catrina"],
    "stormtrooper": ["stormtrooper", "storm trooper"],
}


def hit(label, people):
    keys = ALIASES.get(label, [label.replace("_", " ")])
    # solo el campo character: la descripcion a veces nombra el disfraz aunque el personaje este mal
    text = " ".join(str(p.get("character", "")) for p in people).lower()
    return any(k in text for k in keys)


def run(model):
    if ":" in model:
        describe(cv2.imread(str(IMAGES[0])), model)  # calentamiento: Ollama carga el modelo
    rows, total_t, hits = [], 0.0, 0
    for path in IMAGES:
        label = path.stem.rsplit("_", 1)[0]
        try:
            result, dt = describe(cv2.imread(str(path)), model)
        except Exception as e:  # error de red/API: se cuenta como fallo y se sigue
            result, dt = {"people": [], "error": str(e)}, 0.0
        people = result.get("people", [])
        ok = hit(label, people)
        hits += ok
        total_t += dt
        chars = ", ".join(str(p.get("character", "?")) for p in people) or result.get("error", "-")[:60]
        print(f"{'OK ' if ok else 'XX '} {path.name:22s} {dt:5.1f}s  {chars}")
        rows.append({"image": path.name, "expected": label, "hit": ok, "seconds": round(dt, 2), **result})
    n = len(IMAGES)
    print(f"== {model}: {hits}/{n} aciertos, {total_t / n:.1f} s/imagen\n")
    out = HERE / f"results_{model.replace(':', '_').replace('/', '_')}.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    for m in sys.argv[1:] or ["meta/llama-3.2-90b-vision-instruct"]:
        run(m)
