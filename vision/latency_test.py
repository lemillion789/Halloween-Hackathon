"""Mide si las llamadas al VLM van mas rapido de una en una o en paralelo (recortes de una foto).

Uso: .venv/bin/python latency_test.py test_images/gemini_2.jpeg [--model ...]
"""
import argparse
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
from ultralytics import YOLO

from costume_describer import DEFAULT_MODEL, describe
from person_costume import crop_person


def one(crop, model):
    return describe(crop, model, retry_empty=False)[1]


ap = argparse.ArgumentParser()
ap.add_argument("image")
ap.add_argument("--model", default=DEFAULT_MODEL)
args = ap.parse_args()

frame = cv2.imread(args.image)
boxes = YOLO("yolo11n.pt")(frame, classes=[0], verbose=False)[0].boxes.xyxy.tolist()
crops = [crop_person(frame, b) for b in boxes]
print(f"{len(crops)} recortes, modelo {args.model}")

t0 = time.perf_counter()
times = [one(c, args.model) for c in crops]
print(f"SECUENCIAL: total {time.perf_counter() - t0:.1f}s, por recorte {[round(t, 1) for t in times]}", flush=True)

for workers in (2, len(crops)):
    t0 = time.perf_counter()
    with ThreadPoolExecutor(workers) as pool:
        times = list(pool.map(lambda c: one(c, args.model), crops))
    print(f"PARALELO x{workers}: total {time.perf_counter() - t0:.1f}s, por recorte {[round(t, 1) for t in times]}", flush=True)
