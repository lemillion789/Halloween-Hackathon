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

Kokoro-82M offline + efectos (pedalboard). Voz por defecto (9 nov): `am_michael` con estilo `monster` (tono -5, voz una octava abajo, "varias gargantas", gruñido y saturacion). Otros estilos: `evil_ai` (metalico) y `spooky` (el de la fiesta del 31 oct: `bm_george`, eco y reverb). Pausas dentro del texto: `[p]` = 0.8 s, `[p1.5]` = 1.5 s.

```bash
.venv/Scripts/python tts.py "I see you, Batman"   # --style monster|evil_ai|spooky, --voice, --speed, --pitch, --dry, --out x.wav, --lines frases.txt
.venv/Scripts/python voice_lab.py                 # ventana para escribir frases y ajustar la voz con deslizadores
.venv/bin/python person_costume.py --camera 0 --speak
```

Un token viejo en `~/.cache/huggingface/token` daba 401 al bajar Kokoro; `tts.py` lo ignora (`HF_HUB_DISABLE_IMPLICIT_TOKEN`).

## Agente de voz (`voice_agent.py`)

Conversacion offline: microfono -> Silero VAD -> faster-whisper (`base`, CPU int8; entiende espanol e ingles) -> LLM en Ollama (`qwen3:4b-instruct`, Apache 2.0) -> voz `monster`. Personalidades en `personas.py` (`--persona`): `awakened` (por defecto: calavera que acaba de cobrar vida; los turnos 0-2 confundida y asustada, 3-5 curiosa, 6+ se descubre poderosa y siniestra), `evil_ai` (IA malvada atrapada), `guardian` (guardian de la cripta que pide dulces), `demon` (demonio grunon y bromista), `ghost` (poeta fantasma de 1826), o un `.txt` propio con el prompt. Cada una trae su frase de inicio y sus frases de relleno; las reglas comunes (ingles, largo, moods, limites del concurso) estan en `personas.RULES`. Tras 2 min sin hablar olvida la conversacion (nuevo visitante) pero no la etapa. MEMORIA (`memory.py`): guarda los ultimos 10 intercambios y, tras cada respuesta, el LLM extrae en segundo plano hechos dichos por el visitante (nombre, disfraz, lo que le conto) a `skull_memory.json` (ignorado por git; max 40, sobrevive a reinicios); esos hechos van en el prompt de cada turno. `--reset-memory` la borra, `--no-memory` la desactiva, `--memory archivo.json` usa otra. Responde siempre en ingles, 1-3 frases (una 4a si hace falta), y empieza con una etiqueta de mood (`{evil}`, `{happy}`...) que se manda a los ojos con `--eyes PUERTO` (`M <mood>`). Mientras habla, el microfono se ignora (no se oye a si misma). 1,5 s despues de que terminas de hablar suena una frase de relleno ya sintetizada (`FILLER_DELAY_S`, sin repetir las ultimas) y la respuesta siempre va detras; la respuesta se dice frase a frase mientras el LLM escribe (el primer trozo se corta en la primera coma para empezar antes).

```bash
ollama pull qwen3:4b-instruct
.venv/Scripts/python -m pip install -r requirements-voice.txt   # Linux/Jetson: ver notas dentro del archivo
.venv/Scripts/python voice_agent.py                  # --persona ghost, --list-devices, --mic N, --model llama3.2:3b, --whisper small, --eyes COM7, --no-intro
.venv/Scripts/python voice_agent.py --text "Hola, quien eres?"   # un turno escrito, sin microfono
```

Medido en la laptop (GTX 1650 4 GB, otra app ocupa ~1,5 GB, asi que el LLM va 1/3 en CPU), turno escrito: LLM primera frase 1,2 s, respuesta sonando a los 3,9 s. `llama3.2:3b` cabe mejor en la GPU (primera frase 0,5-0,7 s) pero ignora las etiquetas de mood y se alarga. `qwen3:4b` (sin "instruct") razona en voz alta: no usar.

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

### Musica de fondo (`music.py`)

`game.py` reproduce un loop de Halloween de 24 s generado por codigo (zumbido grave, caja de musica en La menor armonica, campanadas y viento; sin derechos de autor y sin archivos). Baja a ~30 % mientras la calavera habla y sube al callar. Tecla **M** la apaga/enciende. `--music archivo.mp3` usa tu propia pista, `--music-volume 0.5` cambia el volumen y `--no-music` la quita. `.venv/bin/python music.py` lo reproduce en bucle (Ctrl+C para parar) y `music.py --save loop.wav` lo guarda.

Al salir el elegido de la ruleta suena un golpe de terror generado (`music.make_sting`: impacto grave, chillido disonante y campana); la musica cede un instante y el anuncio de la calavera espera ~1.6 s. Para oirlo solo: `.venv/bin/python music.py --sting`.

`--music test_sounds/sound1.mp3` usa una pista tuya: el juego recorta el silencio del principio y del final y funde el final con el inicio para que el loop no tenga hueco. Revisa la licencia de lo que descargues (atribucion, uso comercial) antes de subirlo al repo o usarlo en el video del concurso.

Musica por defecto: `test_sounds/sound1.mp3` si existe (no esta en el repo: licencia sin confirmar); si no, el loop generado. `--music generated` fuerza el generado.

### Voz sincronizada y presentacion de personajes

- El subtitulo aparece cuando el audio realmente empieza (`Speaker.say(texto, on_start)`), no al encolar la frase.
- `game.py` no deja tomar la foto hasta que la voz haya cargado (`Speaker.ready`, ~7 s): antes la primera frase quedaba detras de la carga del modelo.
- `Speaker.prewarm` sintetiza en los ratos libres las frases fijas (esperas, intros) y cada frase en cuanto Nemotron la escribe, asi suenan casi sin retraso.
- Antes de describir a cada persona la calavera dice su numero y un apodo gracioso que Nemotron inventa en la misma llamada: "Victim number one: the hooded one." (los titulos rotan: Victim, Subject, Specimen, Soul, Contestant, Guest). Sin apodo usa el nombre del personaje.

### Pantalla minimalista

En `game.py` el texto solo aparece cuando la calavera dice algo (subtitulos sincronizados con el audio). Al identificar a alguien la tarjeta ya no muestra nombre ni descripcion: cae un sello gracioso (`STAMPS` en game.py: DONE!, FOUND!, WANTED 500 SEK, BUSTED!...). La rueda y el elegido se identifican por numero (#1, #2...), que es el que la calavera dice al presentarlos. Las frases de espera van mas lentas (`WAIT_SPEED`) y con una pausa de `WAIT_PAUSE` s entre una y otra.

### Espera de la API (`hedged`)

El endpoint gratis a veces tarda o deja peticiones colgadas. `costume_describer.hedged()` lanza otro intento en paralelo si no hay respuesta valida a los `hedge_after` s (15 s para el VLM, 8 s para las frases) y se queda con el primero que termine bien; el plazo de las frases es corto (20 s; 14 s el anuncio de la ruleta) y si vence se usa una plantilla. En `game.py` la calavera empieza a presentar a la primera persona en cuanto esta lista (no espera a todas) y rellena con frases de espera si la siguiente tarda. Al cerrar se usa `os._exit` para no esperar a hilos con peticiones colgadas.

Velocidades de voz en `game.py`: frases de espera `WAIT_SPEED` = 0.74 (lentas, con pausa), presentacion de cada persona `PERSON_SPEED` = 0.95 (un poco mas rapida), el resto (ruleta, anuncio) la voz normal de `tts.py` (0.85). Las tarjetas muestran el nombre del disfraz y un sello gracioso; la descripcion solo la dice la calavera.
