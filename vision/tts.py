"""Voz de la calavera: Kokoro-82M (offline) + efectos de terror (tono grave, reverb, eco).

Uso:
  .venv/bin/python tts.py "I see you, Batman"            # habla la frase
  .venv/bin/python tts.py --demo                          # frases de ejemplo
  .venv/bin/python tts.py --out frase.wav "texto"         # guarda en vez de reproducir
  --voice bm_george  --speed 0.8  --pitch -3  --dry (sin efectos)

Desde codigo: speaker = Speaker(); speaker.say("..."); speaker.wait()
"""
import argparse
import os
import queue
import random
import threading

# un token viejo de HF en ~/.cache/huggingface da 401 al bajar un modelo publico: se ignora
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

import numpy as np

SAMPLE_RATE = 24000
VOICE = "bm_george"  # britanico grave; probar bm_lewis, bm_fable, am_onyx, am_fenrir
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


def spooky_line(person):
    """Frase de la calavera para un dict del VLM {character, category, ...}."""
    options = LINES.get(person.get("category"), LINES["default"])
    return random.choice(options).format(c=person.get("character", "stranger"))


def _effects(pitch):
    from pedalboard import Delay, Pedalboard, PitchShift, Reverb
    return Pedalboard([PitchShift(pitch), Delay(delay_seconds=0.18, feedback=0.25, mix=0.18),
                       Reverb(room_size=0.7, damping=0.5, wet_level=0.28, dry_level=0.8)])


class Speaker:
    """Cola de frases en un hilo: no bloquea el video y las frases no se pisan."""

    def __init__(self, voice=VOICE, speed=SPEED, pitch=PITCH, effects=True):
        self.voice, self.speed = voice, speed
        self.fx = _effects(pitch) if effects else None
        self.q = queue.Queue()
        self.pipeline = None
        threading.Thread(target=self._run, daemon=True).start()

    def synth(self, text):
        if self.pipeline is None:
            from kokoro import KPipeline
            self.pipeline = KPipeline(lang_code=self.voice[0], repo_id="hexgrad/Kokoro-82M")
        parts = [np.asarray(audio, dtype=np.float32) for _, _, audio in self.pipeline(text, voice=self.voice, speed=self.speed)]
        audio = np.concatenate(parts + [np.zeros(int(SAMPLE_RATE * 0.8), dtype=np.float32)])  # cola para el eco
        if self.fx is not None:
            audio = self.fx(audio[None, :], SAMPLE_RATE)[0]
        return audio

    def say(self, text):
        self.q.put(text)

    def wait(self):
        self.q.join()

    def idle(self):
        return self.q.unfinished_tasks == 0

    def _run(self):
        import sounddevice as sd
        self.synth("Hello.")  # carga y calienta el modelo al arrancar (~7 s), no en la primera frase
        while True:
            text = self.q.get()
            try:
                print(f'[voz] "{text}"', flush=True)
                sd.play(self.synth(text), SAMPLE_RATE)
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
    ap.add_argument("--pitch", type=float, default=PITCH)
    ap.add_argument("--dry", action="store_true", help="sin efectos")
    ap.add_argument("--out", help="guardar WAV en vez de reproducir")
    args = ap.parse_args()
    speaker = Speaker(args.voice, args.speed, args.pitch, effects=not args.dry)
    texts = [" ".join(args.text)] if args.text else []
    if args.demo:
        texts += [spooky_line({"character": "Batman", "category": "superhero"}),
                  spooky_line({"character": "witch", "category": "fantasy"})]
    if args.out:
        import soundfile as sf
        sf.write(args.out, speaker.synth(texts[0]), SAMPLE_RATE)
        print("guardado", args.out)
        return
    for t in texts:
        speaker.say(t)
    speaker.wait()


if __name__ == "__main__":
    main()
