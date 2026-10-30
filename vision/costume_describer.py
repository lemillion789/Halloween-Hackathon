"""Reconoce y describe disfraces con un modelo de vision-lenguaje.

Modelos (se elige el backend por el nombre):
  - API de NVIDIA (por defecto, nombre con "/", p. ej. meta/llama-3.2-90b-vision-instruct):
    necesita internet y NVIDIA_API_KEY (build.nvidia.com).
  - Local con Ollama (nombre con ":", p. ej. qwen3-vl:2b-instruct): offline, ~18 s/foto en la GTX 1650.
  - API de Claude (claude-*): necesita ANTHROPIC_API_KEY.

Uso:
  .venv/Scripts/python costume_describer.py foto1.jpg foto2.jpg ...   # imagenes sueltas
  .venv/Scripts/python costume_describer.py --camera 0                # webcam (C922): ESPACIO describe, Q sale
  --model qwen3-vl:2b-instruct  para usar el modelo local
"""
import argparse
import base64
import json
import os
import re
import threading
import time

import cv2

DEFAULT_MODEL = "meta/llama-3.2-90b-vision-instruct"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1"
MAX_SIDE = 640  # se reduce la imagen antes de mandarla: mas rapido y casi igual de preciso

PROMPT = """You are the eyes of an animatronic Halloween skull. Look at the people in this photo.
For each visible person (max 4, closest first) say what costume they wear.
- "character": the specific named character if recognizable (e.g. "Spider-Man", "Darth Vader",
  "Harley Quinn"), otherwise a generic type (e.g. "witch", "zombie", "pirate", "vampire").
  Use "no costume" if they wear normal clothes.
- "category": one of superhero, villain, movie/tv, anime/game, monster, undead, fantasy, animal, other, none.
- "description": one short sentence about the costume (colors, props, makeup).
- "confidence": your confidence from 0 to 1 that "character" is right.
If there are no people, return an empty list."""

SCHEMA = {
    "type": "object",
    "properties": {
        "people": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "character": {"type": "string"},
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["character", "category", "description", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["people"],
    "additionalProperties": False,
}

_claude = None
_nvidia = None


def encode(image_bgr):
    h, w = image_bgr.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        image_bgr = cv2.resize(image_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()


def _ask_ollama(jpg, model):
    import ollama

    resp = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": PROMPT, "images": [jpg]}],
        format=SCHEMA,
        options={"temperature": 0, "num_ctx": 4096},
        keep_alive="10m",
    )
    return resp.message.content


def _ask_claude(jpg, model):
    global _claude
    import anthropic

    if _claude is None:
        _claude = anthropic.Anthropic()
    resp = _claude.beta.messages.create(
        model=model,
        max_tokens=4096,
        # si el modelo rechaza la peticion, la API la reintenta con otro modelo
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                             "data": base64.standard_b64encode(jpg).decode()}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )
    if resp.stop_reason == "refusal":
        return json.dumps({"people": [], "raw": "refusal"})
    return next(b.text for b in resp.content if b.type == "text")


def _ask_nvidia(jpg, model):
    global _nvidia
    from openai import OpenAI

    if _nvidia is None:
        _nvidia = OpenAI(base_url=NVIDIA_URL, api_key=os.environ["NVIDIA_API_KEY"])
    b64 = base64.standard_b64encode(jpg).decode()
    prompt = PROMPT + '\nAnswer ONLY with JSON like {"people": [{"character": "...", "category": "...", ' \
                      '"description": "...", "confidence": 0.9}]}'
    resp = _nvidia.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
        temperature=0.1,
        max_tokens=600,
    )
    return resp.choices[0].message.content


def _parse(text):
    """Algunos modelos envuelven el JSON en ```json ...``` o texto: se extrae el primer {...}."""
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        result = json.loads(m.group(0) if m else text)
        result.setdefault("people", [])
        return result
    except (json.JSONDecodeError, AttributeError):
        return {"people": [], "raw": text}


def describe(image_bgr, model=DEFAULT_MODEL):
    """Devuelve ({"people": [...]}, segundos). Backend segun el nombre del modelo (ver arriba)."""
    t0 = time.perf_counter()
    ask = _ask_ollama if ":" in model else _ask_nvidia if "/" in model else _ask_claude
    text = ask(encode(image_bgr), model)
    return _parse(text), time.perf_counter() - t0


def run_camera(index, model):
    # DirectShow solo existe en Windows; en Linux (V4L2) se usa el backend por defecto
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    state = {"text": "ESPACIO = describir, Q = salir", "busy": False}

    def worker(frame):
        try:
            result, dt = describe(frame, model)
            print(f"[{dt:.1f}s] {json.dumps(result, ensure_ascii=False)}")
            people = result.get("people", [])
            state["text"] = f"{' | '.join(p['character'] for p in people) or 'nadie'} ({dt:.1f}s)"
        except Exception as e:  # sin internet, clave invalida, etc.: que no se caiga la camara
            print("Error:", e)
            state["text"] = f"error: {type(e).__name__}"
        state["busy"] = False

    while True:
        ok, frame = cap.read()
        if not ok:
            print("No se pudo leer la camara")
            break
        view = frame.copy()
        text = "pensando..." if state["busy"] else state["text"]
        cv2.putText(view, text[:90], (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow("costume_describer", view)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord(" ") and not state["busy"]:
            state["busy"] = True
            threading.Thread(target=worker, args=(frame.copy(),), daemon=True).start()
    cap.release()
    cv2.destroyAllWindows()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="*")
    ap.add_argument("--camera", type=int)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()
    if args.camera is not None:
        run_camera(args.camera, args.model)
        return
    for path in args.images:
        result, dt = describe(cv2.imread(path), args.model)
        print(f"{path} [{dt:.1f}s]\n{json.dumps(result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
