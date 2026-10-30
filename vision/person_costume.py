"""Detecta personas con YOLO, las sigue (tracker) y describe el disfraz de cada una una sola vez.

Flujo: camara -> YOLO + ByteTrack -> recorte por persona -> VLM (costume_describer.describe) -> etiqueta
sobre la caja. El VLM se llama una vez por ID de persona, en hilos, asi el video no se frena.

Uso:
  .venv/bin/python person_costume.py --camera 0            # C922 o webcam; R = volver a describir todos, Q = salir
  .venv/bin/python person_costume.py --source foto.jpg     # imagen suelta
  --speak  la calavera dice una frase de terror por cada persona nueva (voz: tts.py)
  --model <nombre>   para cambiar de modelo (por defecto Nemotron, ver costume_describer.DEFAULT_MODEL)
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
from ultralytics import YOLO

from costume_describer import DEFAULT_MODEL, describe
from skull_lines import filler, write_line
from tts import Speaker

MIN_FRAMES = 8      # frames seguidos antes de describir (evita falsos positivos fugaces)
MIN_HEIGHT = 0.30   # la persona debe ocupar al menos este % del alto del frame
MARGIN = 0.10       # margen extra alrededor del recorte
RETRY_AFTER = 8.0   # segundos antes de reintentar si la API fallo
MAX_WORKERS = 6     # llamadas simultaneas al VLM: el endpoint las atiende en paralelo (medido); limite del plan gratis 40 rpm
FILLER_EVERY = 12.0  # segundos minimos entre frases de relleno
NO_COSTUME = {"character": "no costume", "category": "none", "description": "", "confidence": 1.0}
LOG_PATH = "person_costume.log.jsonl"


def crop_person(frame, box):
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = box
    mx, my = (x2 - x1) * MARGIN, (y2 - y1) * MARGIN
    x1, y1 = max(0, int(x1 - mx)), max(0, int(y1 - my))
    x2, y2 = min(w, int(x2 + mx)), min(h, int(y2 + my))
    return frame[y1:y2, x1:x2].copy()


class CostumeTracker:
    def __init__(self, model, speaker=None):
        self.model = model
        self.speaker = speaker
        self.pool = ThreadPoolExecutor(MAX_WORKERS)
        self.seen = {}      # id -> frames vistos
        self.info = {}      # id -> dict con character/description/... ya resuelto
        self.pending = {}   # id -> future
        self.retry_at = {}  # id -> timestamp
        self.last_filler = 0.0

    def _job(self, tid, crop):
        print(f"#{tid}: enviando recorte {crop.shape[1]}x{crop.shape[0]} a {self.model}...", flush=True)
        result, dt = describe(crop, self.model)
        people = result.get("people", [])
        person = people[0] if people else NO_COSTUME  # sin respuesta tras el reintento = no se pudo identificar
        speech = write_line(person, self.model) if self.speaker else None
        entry = {"id": tid, "seconds": round(dt, 1), "model": self.model, "person": person, "line": speech}
        print(json.dumps(entry, ensure_ascii=False))
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return person, dt, speech

    def update(self, frame, ids, boxes):
        """Lanza la descripcion de personas nuevas y recoge las que ya terminaron."""
        now = time.time()
        for tid, box in zip(ids, boxes):
            self.seen[tid] = self.seen.get(tid, 0) + 1
            if tid in self.info or tid in self.pending:
                continue
            tall = (box[3] - box[1]) / frame.shape[0] >= MIN_HEIGHT
            if self.seen[tid] >= MIN_FRAMES and tall and now >= self.retry_at.get(tid, 0):
                self.pending[tid] = self.pool.submit(self._job, tid, crop_person(frame, box))
                self.say_filler(now)
        for tid, fut in list(self.pending.items()):
            if not fut.done():
                continue
            del self.pending[tid]
            try:
                person, dt, speech = fut.result()
            except Exception as e:  # sin internet, limite de la API, etc.
                print(f"Error id {tid}: {type(e).__name__}: {e}")
                self.retry_at[tid] = now + RETRY_AFTER
                continue
            self.info[tid] = {**person, "seconds": dt}
            if self.speaker and speech:
                self.speaker.say(speech)

    def say_filler(self, now):
        """Frase inmediata mientras el VLM piensa; solo si la calavera esta callada y no hubo otra hace poco."""
        if self.speaker and self.speaker.idle() and now - self.last_filler > FILLER_EVERY:
            self.last_filler = now
            self.speaker.say(filler())

    def label(self, tid):
        if tid in self.info:
            p = self.info[tid]
            return f"#{tid} {p['character']} ({p['confidence']:.0%}, {p['seconds']:.0f}s)"
        return f"#{tid} pensando..." if tid in self.pending else f"#{tid}"

    def reset(self):
        self.info.clear()
        self.retry_at.clear()


def draw(frame, ids, boxes, tracker):
    for tid, (x1, y1, x2, y2) in zip(ids, boxes):
        color = (0, 200, 0) if tid in tracker.info else (0, 165, 255)
        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        cv2.putText(frame, tracker.label(tid)[:50], (int(x1), max(20, int(y1) - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def run_camera(index, model, yolo_name, speaker=None):
    yolo = YOLO(yolo_name)
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    tracker = CostumeTracker(model, speaker)
    while True:
        ok, frame = cap.read()
        if not ok:
            print("No se pudo leer la camara")
            break
        res = yolo.track(frame, classes=[0], persist=True, verbose=False, tracker="bytetrack.yaml")[0]
        ids, boxes = [], []
        if res.boxes.id is not None:
            ids = res.boxes.id.int().tolist()
            boxes = res.boxes.xyxy.tolist()
        tracker.update(frame, ids, boxes)
        view = frame.copy()
        draw(view, ids, boxes, tracker)
        cv2.imshow("person_costume", view)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("r"):
            tracker.reset()
    cap.release()
    cv2.destroyAllWindows()


def run_image(path, model, yolo_name, speaker=None):
    """Una foto: detecta, describe cada persona en paralelo y guarda <foto>_out.jpg."""
    frame = cv2.imread(path)
    res = YOLO(yolo_name)(frame, classes=[0], verbose=False)[0]
    boxes = res.boxes.xyxy.tolist()
    tracker = CostumeTracker(model, speaker)
    futures = {i + 1: tracker.pool.submit(tracker._job, i + 1, crop_person(frame, b)) for i, b in enumerate(boxes)}
    tracker.say_filler(time.time())
    for tid, fut in futures.items():
        try:
            person, dt, speech = fut.result()
        except Exception as e:
            print(f"#{tid}: error {type(e).__name__}: {e}")
            continue
        tracker.info[tid] = {**person, "seconds": dt}
        if speaker and speech:
            speaker.say(speech)
    draw(frame, list(futures), boxes, tracker)
    out = path.rsplit(".", 1)[0] + "_out.jpg"
    cv2.imwrite(out, frame)
    print(f"{len(boxes)} personas -> {out}")
    if speaker:
        speaker.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int)
    ap.add_argument("--source", help="imagen suelta")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--yolo", default="yolo11n.pt")
    ap.add_argument("--speak", action="store_true", help="la calavera dice una frase por persona nueva")
    args = ap.parse_args()
    speaker = Speaker() if args.speak else None
    if args.source:
        run_image(args.source, args.model, args.yolo, speaker)
    else:
        run_camera(args.camera if args.camera is not None else 0, args.model, args.yolo, speaker)


if __name__ == "__main__":
    main()
