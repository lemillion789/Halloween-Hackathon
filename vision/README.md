# Reconocer disfraces

La calavera mira a quien tiene enfrente y dice de qué va disfrazado ("¡Un Joker!").
Un modelo de visión-lenguaje recibe la foto y devuelve JSON:

```json
{"people": [{"character": "Joker", "category": "villain",
             "description": "purple suit, green hair, white face paint", "confidence": 0.9}]}
```

## Instalación (Windows)

```bash
py -3.12 -m venv vision/.venv
vision/.venv/Scripts/python -m pip install requests opencv-python pillow ollama openai anthropic
```

En Linux:

```bash
python3 -m venv vision/.venv
vision/.venv/bin/python -m pip install requests opencv-python pillow ollama openai anthropic
export NVIDIA_API_KEY="nvapi-..."   # o ponerlo en ~/.bashrc
```

y usar `.venv/bin/python` en lugar de `.venv/Scripts/python`.

## Backends

El backend se elige por el nombre del modelo (`--model`):

| Nombre | Backend | Necesita |
|---|---|---|
| con `/` (por defecto `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`) | API de NVIDIA, build.nvidia.com | internet + `NVIDIA_API_KEY` |
| con `:` (p. ej. `qwen3-vl:2b-instruct`) | Ollama local | `ollama pull <modelo>` |
| `claude-*` | API de Claude | internet + `ANTHROPIC_API_KEY` |

Clave de NVIDIA en Windows (en tu terminal; queda para las terminales nuevas):

```bash
setx NVIDIA_API_KEY "nvapi-..."
```

## Uso

```bash
cd vision
.venv/Scripts/python costume_describer.py test_images/joker_2.jpg
.venv/Scripts/python costume_describer.py --camera 0          # C922: ESPACIO describe, Q sale
.venv/Scripts/python benchmark.py meta/llama-3.2-90b-vision-instruct meta/llama-3.2-11b-vision-instruct
```

`benchmark.py` usa las fotos de `test_images/`; el nombre del archivo es la respuesta esperada.
Cuenta como acierto solo el campo `character`. Guarda `results_<modelo>.json`.
Las fotos se bajan de Wikimedia Commons con `fetch_test_images.py`, que guarda autor y licencia en `test_images/credits.json`.

## Resultados (laptop: i5-10300H, GTX 1650 4 GB, 24 GB RAM)

| Modelo | Aciertos | s/foto | Notas |
|---|---|---|---|
| qwen3-vl:2b-instruct (Ollama) | 15/18 | ~18 | 16 s solo en procesar imagen+prompt; 20 % del modelo en CPU |
| qwen3-vl:4b-instruct (Ollama) | - | >18 | 54 % en CPU; prueba cancelada |
| nvidia/nemotron-3-nano-omni-30b-a3b-reasoning (API NVIDIA) | 15/18 | ~5.5 (1-3 s con una persona, hasta 10 s con grupos) | `reasoning_budget` 1024, reintenta si la lista viene vacia. Fallan darth_vader_1, pikachu_1 (lista vacia) y skeleton_1 ("no costume") |
| Llama 3.2 Vision (11b/90b) | no usable | | Licencia excluye la UE (Suecia) |

Conclusión: en esta GPU un VLM local no baja de 10 s. Para jugar se usa la API.
Para el concurso, que tiene que ser 100 % offline, la idea es CLIP para nombrar el personaje rápido y el VLM en la Jetson para la descripción.

## Pipeline con varias personas (`person_costume.py`)

YOLO11n + ByteTrack detectan personas, se recorta cada una y el VLM se llama una vez por ID (hilos, max 6 a la vez; el plan gratis permite 40 rpm). Etiqueta verde = ya descrita; `R` vuelve a describir a todos.

```bash
.venv/bin/python person_costume.py --camera 0 --model nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
.venv/bin/python person_costume.py --source foto.jpg
```

Nemotron a veces devuelve listas sueltas, JSON repetido o cortado; `_parse` junta los objetos completos.
Al hablar, evitar detalles de armas del VLM (reglas del concurso: sin violencia realista).

## Voz (`tts.py`)

Kokoro-82M offline + efectos de terror (pedalboard: tono -2 semitonos, eco, reverb), voz `bm_george`. Solo para la fiesta del 31 oct en la laptop; para el concurso se cambiara por otro modelo local.

```bash
.venv/bin/python tts.py "I see you, Batman"   # --demo, --voice bm_george, --speed 0.8, --pitch -3, --dry, --out x.wav
.venv/bin/python person_costume.py --camera 0 --speak
```

Un token viejo en `~/.cache/huggingface/token` daba 401 al bajar Kokoro; `tts.py` lo ignora (`HF_HUB_DISABLE_IMPLICIT_TOKEN`).

## Frases (`skull_lines.py`)

Con `--speak`: al detectar a alguien nuevo la calavera dice un relleno al instante ("Hmm... what do we have here..."; solo si esta callada y no hubo otro hace 12 s); cuando el VLM termina, Nemotron escribe una frase segun el disfraz (segunda llamada, solo texto, `reasoning_budget` 128, timeout 20 s). Si no se identifica el disfraz ("no costume", lista vacia tras el reintento o confianza < 0.3) dice una frase sarcastica sobre no tener disfraz. Si la API falla usa plantillas. El prompt prohibe armas, violencia e insultos personales (reglas del concurso). Cada frase queda en `person_costume.log.jsonl`.

## Ruleta (`roulette.py`)

Con la camara y `--speak`, tecla **S**: la ruleta recorre a las personas ya descritas que estan en pantalla (minimo 2), frena poco a poco en una (caja amarilla girando, roja al elegir) y la calavera anuncia con una frase de Nemotron que debe cumplir un reto. Por defecto `--dare "take a shot"` (solo para la fiesta); para el video del concurso usar otro reto, p. ej. `--dare "do your best villain laugh"`. Si la API falla usa frases de respaldo.

## Modo juego (`game.py`, pygame)

Foto -> YOLO separa a las personas -> cada una vuela a una tarjeta -> el VLM las describe (la tarjeta gira al llegar el resultado) -> la calavera las presenta de izquierda a derecha con subtitulos y mandibula -> tecla S: ruleta con la cara de cada participante, puntero con tictac y el elegido sube al centro con su reto.

```bash
.venv/bin/python game.py --source test_images/gemini_2.jpeg   # la imagen hace de camara
.venv/bin/python game.py --camera 0
# --mute (sin voz) --dare "take a shot" --speed 2 (anima mas rapido)
```
Teclas: ESPACIO foto, S ruleta (repetir), R nueva foto, ESC salir. Probado con descripciones simuladas (capturas headless); falta probar con la API y la voz reales.
