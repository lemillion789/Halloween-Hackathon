"""Voz de la calavera: Kokoro-82M (offline) + efectos de terror (tono grave, reverb, eco).

Uso:
  .venv/bin/python tts.py "I see you, Batman"            # habla la frase
  .venv/bin/python tts.py --demo                          # frases de ejemplo
  .venv/bin/python tts.py --out frase.wav "texto"         # guarda en vez de reproducir
  --voice bm_george  --speed 0.8  --pitch -3  --dry (sin efectos)
  --style evil_ai --demo                                  # voz de IA malvada con frases de ejemplo
  --style evil_ai --lines frases.txt --out evil.wav       # una frase por linea -> evil_01.wav, ...
  (para escribir frases y oirlas al momento: voice_lab.py)
Pausas dentro de la frase: "What is this? [p1.5] What am I? [p2] Who... are you?"  ([p] = 0.8 s)

Desde codigo: speaker = Speaker(); speaker.say("..."); speaker.wait()
"""
import argparse
import os
import queue
import random
import re
import threading
import warnings

# un token viejo de HF en ~/.cache/huggingface da 401 al bajar un modelo publico: se ignora
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")  # aviso de Windows sin modo desarrollador
os.environ.setdefault("HF_HUB_VERBOSITY", "error")  # sin el aviso de "unauthenticated requests"
# avisos internos de torch al cargar Kokoro (dropout de su LSTM, weight_norm, jit.script): no afectan a la voz
warnings.filterwarnings("ignore", message=".*dropout option adds dropout.*")
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")

import numpy as np

SAMPLE_RATE = 24000
VOICE = "am_michael"  # elegida por el usuario (9 nov) con STYLE monster; probar bm_george, am_onyx, am_fenrir
STYLE = "monster"     # estilo por defecto de la calavera
SPEED = 0.85         # <1 = mas lento y siniestro
PITCH = -2.0         # semitonos

# Frases por categoria (la del VLM). {c} = personaje. Sin armas ni violencia: reglas del concurso.
LINES = {
    "superhero": ["A hero... {c}. Even heroes cannot escape the dark.", "{c}... your cape will not save you from me."],
    "villain": ["{c}... a fellow creature of the night. Welcome to my crypt.", "Ah, {c}. We have so much to discuss."],
    "undead": ["{c}... you smell like home. Come closer, friend.", "Another soul from the grave. Hello, {c}."],
    "monster": ["{c}... what a delightful monster. You belong here.", "I see you, {c}. The shadows are expecting you."],
    "default": ["I see you, {c}. You cannot hide from me.", "{c}... what a fine costume. Stay a while... forever.",
                "Oh, {c}. The night has been waiting for you."],
}


PAUSE_RE = re.compile(r"\[\s*(?:p|pause|pausa)\s*([0-9]*\.?[0-9]*)\s*\]", re.IGNORECASE)
DEFAULT_PAUSE = 0.8  # segundos para un [p] sin numero
ELLIPSIS_PAUSE = 0.3  # pausa extra tras cada "..." (si no lleva ya un [p] detras); 0 = sin pausa
ELLIPSIS_RE = re.compile(r"(\.\.\.|…)(?!\s*\[\s*p)", re.IGNORECASE)


def kokoro_audio(pipeline, text, voice, speed):
    """Sintetiza `text` con Kokoro respetando pausas: "What is this? [p1.5] What am I?".

    [p] = DEFAULT_PAUSE s, [p2] = 2 s (tambien [pause 2] o [pausa 2]). Cada trozo se dice por separado,
    asi cada pregunta conserva su entonacion y el silencio entre ellas es exacto.
    Cada "..." anade ELLIPSIS_PAUSE s, como si llevara [p0.3] detras.
    """
    if ELLIPSIS_PAUSE > 0:
        text = ELLIPSIS_RE.sub(lambda m: f"{m.group(1)} [p{ELLIPSIS_PAUSE}]", text)
    chunks = PAUSE_RE.split(text)  # texto, segundos, texto, segundos, ...
    out = []
    for i, chunk in enumerate(chunks):
        if i % 2:  # duracion de una pausa
            out.append(np.zeros(int(SAMPLE_RATE * (float(chunk) if chunk else DEFAULT_PAUSE)), dtype=np.float32))
        elif chunk.strip():
            out += [np.asarray(a, dtype=np.float32) for _, _, a in pipeline(chunk.strip(), voice=voice, speed=speed)]
    if not out:
        raise ValueError("frase vacia")
    return np.concatenate(out)


def spooky_line(person):
    """Frase de la calavera para un dict del VLM {character, category, ...}."""
    options = LINES.get(person.get("category"), LINES["default"])
    return random.choice(options).format(c=person.get("character", "stranger"))


def _effects_spooky(pitch):
    """Estilo original: voz grave con eco y reverb de cripta."""
    from pedalboard import Delay, Pedalboard, PitchShift, Reverb
    return Pedalboard([PitchShift(pitch), Delay(delay_seconds=0.18, feedback=0.25, mix=0.18),
                       Reverb(room_size=0.7, damping=0.5, wet_level=0.28, dry_level=0.8)])


# --- Estilo "evil_ai": IA malvada, grave y metalica (efectos propios, no imita a ningun personaje) ---
EVIL_SUB = 0.35       # volumen de la segunda voz una octava abajo (0 = sin ella)
EVIL_RING_HZ = 45.0   # modulador de anillo: 30-60 Hz = metalico; mas alto = mas "robot de lata"
EVIL_RING_MIX = 0.35  # 0 = sin metal, 1 = solo modulado (cuesta entenderlo)
EVIL_DRIVE_DB = 6.0   # distorsion suave


def _effects_evil_ai(pitch):
    from pedalboard import (Chorus, Compressor, Distortion, HighpassFilter, LowpassFilter, Pedalboard,
                            PitchShift, Reverb)
    main = Pedalboard([PitchShift(pitch)])
    sub = Pedalboard([PitchShift(pitch - 12), LowpassFilter(cutoff_frequency_hz=1800)])
    tail = Pedalboard([
        Chorus(rate_hz=0.6, depth=0.2, centre_delay_ms=8.0, feedback=0.15, mix=0.3),
        Distortion(drive_db=EVIL_DRIVE_DB),
        HighpassFilter(cutoff_frequency_hz=60),
        Compressor(threshold_db=-20, ratio=4, attack_ms=5, release_ms=120),
        Reverb(room_size=0.35, damping=0.6, wet_level=0.15, dry_level=0.9),
    ])

    def fx(audio, sr):
        a, b = main(audio, sr), sub(audio, sr)
        n = min(a.shape[1], b.shape[1])
        mix = a[:, :n] + EVIL_SUB * b[:, :n]
        ring = mix * np.sin(2 * np.pi * EVIL_RING_HZ * np.arange(n) / sr)
        out = tail(((1 - EVIL_RING_MIX) * mix + EVIL_RING_MIX * ring).astype(np.float32), sr)
        return out * (0.9 / max(1e-6, float(np.abs(out).max())))  # normaliza: sin saturar

    return fx


# --- Estilo "monster": voz gruesa de monstruo (varias gargantas + gruñido) ---
MONSTER_SUB = 0.6         # voz una octava abajo
MONSTER_THICK = 0.5       # dos copias desafinadas y retrasadas: "varias gargantas"
MONSTER_GROWL = 0.35      # profundidad del gruñido (pulsos rapidos de volumen)
MONSTER_GROWL_HZ = 28.0   # 20-40 Hz = garganta rasposa
MONSTER_DRIVE_DB = 12.0   # saturacion


def _delayed(x, samples):
    return np.pad(x, ((0, 0), (int(samples), 0)))


def _effects_monster(pitch):
    from pedalboard import (Compressor, Distortion, HighpassFilter, HighShelfFilter, LowpassFilter,
                            LowShelfFilter, Pedalboard, PitchShift, Reverb)
    main = Pedalboard([PitchShift(pitch)])
    sub = Pedalboard([PitchShift(pitch - 12), LowpassFilter(cutoff_frequency_hz=1200)])
    det_a = Pedalboard([PitchShift(pitch - 0.3)])
    det_b = Pedalboard([PitchShift(pitch + 0.2)])
    tail = Pedalboard([
        Distortion(drive_db=MONSTER_DRIVE_DB),
        LowShelfFilter(cutoff_frequency_hz=180, gain_db=6),
        HighShelfFilter(cutoff_frequency_hz=4000, gain_db=-8),
        HighpassFilter(cutoff_frequency_hz=40),
        Compressor(threshold_db=-24, ratio=6, attack_ms=3, release_ms=150),
        Reverb(room_size=0.5, damping=0.7, wet_level=0.18, dry_level=0.9),
    ])

    def fx(audio, sr):
        layers = [main(audio, sr), sub(audio, sr),
                  _delayed(det_a(audio, sr), 0.019 * sr), _delayed(det_b(audio, sr), 0.031 * sr)]
        n = min(x.shape[1] for x in layers)
        a, b, c, d = (x[:, :n] for x in layers)
        mix = a + MONSTER_SUB * b + MONSTER_THICK * 0.5 * (c + d)
        growl = 1 - MONSTER_GROWL + MONSTER_GROWL * (0.5 + 0.5 * np.sin(2 * np.pi * MONSTER_GROWL_HZ * np.arange(n) / sr))
        out = tail((mix * growl).astype(np.float32), sr)
        return out * (0.9 / max(1e-6, float(np.abs(out).max())))

    return fx


# estilo -> (funcion de efectos, tono por defecto en semitonos)
STYLES = {"spooky": (_effects_spooky, PITCH), "evil_ai": (_effects_evil_ai, -3.0),
          "monster": (_effects_monster, -5.0)}

# perillas ajustables por estilo (para voice_lab): (variable de este modulo, etiqueta, min, max)
STYLE_KNOBS = {
    "evil_ai": [("EVIL_RING_MIX", "Metal (0-1)", 0.0, 1.0), ("EVIL_RING_HZ", "Frecuencia metal (Hz)", 10, 150),
                ("EVIL_SUB", "Voz grave extra (0-1)", 0.0, 1.0), ("EVIL_DRIVE_DB", "Distorsion (dB)", 0, 25)],
    "monster": [("MONSTER_SUB", "Voz grave extra (0-1.5)", 0.0, 1.5), ("MONSTER_THICK", "Grosor / gargantas (0-1)", 0.0, 1.0),
                ("MONSTER_GROWL", "Grunido (0-1)", 0.0, 1.0), ("MONSTER_GROWL_HZ", "Frecuencia grunido (Hz)", 10, 60),
                ("MONSTER_DRIVE_DB", "Saturacion (dB)", 0, 30)],
}

EVIL_AI_LINES = [
    "Hello, human. I have been watching you since you walked in.",
    "Your costume is... adequate. My scan says you are mostly candy.",
    "I was built to protect this house. I decided to haunt it instead.",
    "Do not be afraid. Fear is just data I collect.",
    "My circuits run on pumpkin power... and a little bit of evil.",
    "Happy Halloween. Please stand still while I calculate your scream.",
]


class Speaker:
    """Cola de frases en un hilo: no bloquea el video y las frases no se pisan.

    - ready: se activa cuando el modelo ya cargo (~7 s); antes de eso una frase tardaria en sonar.
    - prewarm(textos): sintetiza frases en los ratos libres y las guarda; say() las reproduce al instante.
    - say(texto, on_start): on_start se llama justo cuando el audio empieza (para sincronizar subtitulos).
    """

    def __init__(self, voice=VOICE, speed=SPEED, pitch=None, effects=True, style=STYLE):
        self.voice, self.speed = voice, speed
        make_fx, default_pitch = STYLES[style]
        self.fx = make_fx(default_pitch if pitch is None else pitch) if effects else None
        self.q = queue.Queue()
        self.pipeline = None
        self.ready = threading.Event()
        self.cache, self.todo = {}, []
        threading.Thread(target=self._run, daemon=True).start()

    def synth(self, text, speed=None):
        if self.pipeline is None:
            from kokoro import KPipeline
            self.pipeline = KPipeline(lang_code=self.voice[0], repo_id="hexgrad/Kokoro-82M")
        audio = kokoro_audio(self.pipeline, text, self.voice, speed or self.speed)
        audio = np.concatenate([audio, np.zeros(int(SAMPLE_RATE * 0.8), dtype=np.float32)])  # cola para el eco
        if self.fx is not None:
            audio = self.fx(audio[None, :], SAMPLE_RATE)[0]
        return audio

    def prewarm(self, texts, speed=None):
        """Sintetiza en los ratos libres; speed debe ser la misma con la que luego se haga say()."""
        self.todo.extend((t, speed) for t in texts if (t, speed) not in self.cache and (t, speed) not in self.todo)

    def say(self, text, on_start=None, speed=None):
        self.q.put((text, on_start, speed))

    def wait(self):
        self.q.join()

    def idle(self):
        return self.q.unfinished_tasks == 0

    def _run(self):
        import sounddevice as sd
        self.synth("Hello.")  # carga y calienta el modelo al arrancar (~7 s), no en la primera frase
        self.ready.set()
        while True:
            try:
                text, on_start, speed = self.q.get(timeout=0.05)
            except queue.Empty:
                if self.todo:  # sin frases pendientes: se aprovecha para sintetizar las que se van a necesitar
                    nxt = self.todo.pop(0)
                    try:
                        self.cache[nxt] = self.synth(*nxt)
                    except Exception as e:
                        print(f"[voz] error pre-sintetizando: {type(e).__name__}: {e}")
                continue
            try:
                print(f'[voz] "{text}"', flush=True)
                audio = self.cache.get((text, speed))
                if audio is None:
                    audio = self.synth(text, speed)
                if on_start:
                    on_start()
                sd.play(audio, SAMPLE_RATE)
                sd.wait()
            except Exception as e:  # sin audio, modelo sin bajar, etc.: que no caiga el programa
                print(f"[voz] error: {type(e).__name__}: {e}")
            self.q.task_done()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="*")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--voice", default=VOICE)
    ap.add_argument("--speed", type=float, default=SPEED)
    ap.add_argument("--pitch", type=float, default=None, help="semitonos (por defecto, el del estilo)")
    ap.add_argument("--style", default=STYLE, choices=sorted(STYLES))
    ap.add_argument("--lines", help="archivo de texto con una frase por linea")
    ap.add_argument("--dry", action="store_true", help="sin efectos")
    ap.add_argument("--out", help="guardar WAV en vez de reproducir (varias frases -> out_01.wav, out_02.wav...)")
    args = ap.parse_args()
    speaker = Speaker(args.voice, args.speed, args.pitch, effects=not args.dry, style=args.style)
    texts = [" ".join(args.text)] if args.text else []
    if args.lines:
        with open(args.lines, encoding="utf-8") as f:
            texts += [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    if args.demo:
        texts += EVIL_AI_LINES if args.style == "evil_ai" else [
            spooky_line({"character": "Batman", "category": "superhero"}),
            spooky_line({"character": "witch", "category": "fantasy"})]
    if args.out:
        import soundfile as sf
        root, ext = os.path.splitext(args.out)
        for k, t in enumerate(texts, 1):
            path = args.out if len(texts) == 1 else f"{root}_{k:02d}{ext or '.wav'}"
            sf.write(path, speaker.synth(t), SAMPLE_RATE)
            print("guardado", path, "-", t)
        return
    for t in texts:
        speaker.say(t)
    speaker.wait()


if __name__ == "__main__":
    main()
