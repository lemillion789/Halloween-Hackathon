"""Descarga fotos de prueba de disfraces desde Wikimedia Commons (licencias libres).

El nombre de cada archivo es la etiqueta esperada (lo que el modelo deberia reconocer).
Uso: .venv/Scripts/python fetch_test_images.py
"""
import json
import pathlib
import time

import requests

OUT = pathlib.Path(__file__).parent / "test_images"
API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "HalloweenSkullBot/0.1 (element14 hackathon test)"}

# etiqueta esperada -> busqueda en Commons
QUERIES = {
    "spider-man": "Spider-Man cosplay",
    "darth_vader": "Darth Vader cosplay",
    "witch": "witch costume halloween",
    "harley_quinn": "Harley Quinn cosplay",
    "zombie": "zombie walk makeup",
    "pikachu": "Pikachu cosplay",
    "skeleton": "skeleton costume halloween",
    "wonder_woman": "Wonder Woman cosplay",
    "joker": "Joker cosplay",
    "pirate": "pirate costume",
    "stormtrooper": "Stormtrooper costume",
    "vampire": "vampire costume halloween",
}
PER_QUERY = 2
THUMB_W = 800


def search(query, n):
    r = requests.get(API, headers=HEADERS, timeout=30, params={
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": n * 3,
        "prop": "imageinfo", "iiprop": "url|extmetadata|mime", "iiurlwidth": THUMB_W,
    })
    pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p["index"])
    hits = [p for p in pages if p["imageinfo"][0]["mime"] in ("image/jpeg", "image/png")]
    return hits[:n]


def download(url, path, tries=5):
    """Wikimedia limita la tasa (429): reintenta con pausa y valida que sea una imagen."""
    for i in range(tries):
        r = requests.get(url, headers=HEADERS, timeout=60)
        if r.ok and r.headers.get("content-type", "").startswith("image/"):
            path.write_bytes(r.content)
            time.sleep(1)
            return True
        time.sleep(20 * (i + 1))
    return False


def main():
    OUT.mkdir(exist_ok=True)
    credits = {}
    for label, query in QUERIES.items():
        for i, page in enumerate(search(query, PER_QUERY)):
            info = page["imageinfo"][0]
            name = f"{label}_{i + 1}.jpg"
            if (OUT / name).exists() and (OUT / name).read_bytes()[:2] == b"\xff\xd8":
                pass  # ya descargada
            elif not download(info["thumburl"], OUT / name):
                print(f"{name:24s} FALLO")
                continue
            meta = info.get("extmetadata", {})
            credits[name] = {
                "source": info["descriptionurl"],
                "author": meta.get("Artist", {}).get("value", ""),
                "license": meta.get("LicenseShortName", {}).get("value", ""),
            }
            print(f"{name:24s} <- {page['title']}")
    (OUT / "credits.json").write_text(json.dumps(credits, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
