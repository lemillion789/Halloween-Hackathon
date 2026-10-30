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

## Backends

El backend se elige por el nombre del modelo (`--model`):

| Nombre | Backend | Necesita |
|---|---|---|
| con `/` (por defecto `meta/llama-3.2-90b-vision-instruct`) | API de NVIDIA, build.nvidia.com | internet + `NVIDIA_API_KEY` |
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
| API de NVIDIA | pendiente | | |

Conclusión: en esta GPU un VLM local no baja de 10 s. Para jugar se usa la API.
Para el concurso, que tiene que ser 100 % offline, la idea es CLIP para nombrar el personaje rápido y el VLM en la Jetson para la descripción.
