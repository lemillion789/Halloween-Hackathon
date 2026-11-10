"""Agente de voz de la calavera: microfono -> Silero VAD -> Whisper -> LLM local (Ollama) -> voz monster (Kokoro).

Personalidad: ver personas.py (por defecto "awakened": calavera que acaba de cobrar vida, confundida al principio y
cada vez mas siniestra). Entiende espanol e ingles; responde en ingles.
Todo local (offline) salvo la primera descarga de modelos.

Uso (Windows: .venv/Scripts/python, Linux/Jetson: .venv/bin/python):
  python voice_agent.py                       # conversar por el microfono por defecto
  python voice_agent.py --list-devices        # ver microfonos
  python voice_agent.py --mic 12              # elegir microfono
  python voice_agent.py --text "Hola, quien eres?"   # un turno escrito, sin microfono (para probar)
  --model qwen3:4b-instruct  modelo de Ollama        --whisper base   tiny/base/small (mas grande = mejor y mas lento)
  --eyes COM7        manda el mood a los ojos (`M <mood>`) mientras habla
  --persona awakened  personalidad: awakened, evil_ai, guardian, demon, ghost, o un archivo .txt con la tuya
  --no-intro         sin la frase de despertar
  --reset-memory     olvida todo lo recordado (skull_memory.json); --no-memory = sin memoria a largo plazo
Ctrl+C para salir.

Flujo de un turno: el VAD detecta que terminaste de hablar -> Whisper transcribe -> a los 1.5 s suena una
frase de relleno ya sintetizada -> el LLM responde en streaming y cada frase se sintetiza y suena en cuanto
esta completa. Mientras la calavera habla el microfono se ignora (si no, se oiria a si misma).
"""
import argparse
import collections
import os
import queue
import random
import re
import socket
import threading
import time
import unicodedata

import numpy as np

import memory
import personas
import tts  # voz (am_michael + monster), pausas [p], silencia avisos de torch

MIC_SR = 16000
BLOCK = 512  # 32 ms a 16 kHz: el tamano que pide Silero VAD
MAX_UTTERANCE_S = 15

DEFAULT_MODEL = "qwen3:4b-instruct"  # Apache 2.0; respeta mood y [p]. Mas rapido pero sin moods: llama3.2:3b
MAX_SENTENCES = 3
LOCK_PORT = 47613  # puerto local que solo sirve para impedir dos agentes a la vez
FILLER_DELAY_S = 1.5  # el relleno suena este rato despues de que el visitante deja de hablar
FORGET_AFTER_S = 120  # sin hablar este rato se olvida la conversacion (nuevo visitante); la etapa se mantiene

MOODS = ["evil", "angry", "happy", "suspicious", "surprised", "sad", "scared", "possessed"]

# frases que Whisper "oye" en el silencio o el ruido
HALLUCINATIONS = {"thank you.", "thanks for watching!", "thanks for watching.", "gracias.", "you", "bye.",
                  "subtitulos realizados por la comunidad de amara.org", "subtítulos realizados por la comunidad de amara.org"}


def log(tag, msg):
    print(f"[{time.strftime('%H:%M:%S')}] [{tag}] {msg}", flush=True)


class Voice:
    """Dos hilos: uno sintetiza frases (Kokoro + efectos) y otro las reproduce en orden, sin huecos."""

    def __init__(self, voice=tts.VOICE, speed=tts.SPEED, style=tts.STYLE):
        from kokoro import KPipeline
        self.voice, self.speed = voice, speed
        self.pipeline = KPipeline(lang_code=voice[0], repo_id="hexgrad/Kokoro-82M")
        make_fx, pitch = tts.STYLES[style]
        self.fx = make_fx(pitch)
        self.texts, self.audio = queue.Queue(), queue.Queue()
        self.lock = threading.Lock()
        self.pending = 0          # frases encoladas o sonando
        self.last_end = 0.0       # cuando termino de sonar la ultima
        self.on_first_audio = None  # callback(texto) al empezar a sonar una frase "real" (no relleno)
        threading.Thread(target=self._synth_loop, daemon=True).start()
        threading.Thread(target=self._play_loop, daemon=True).start()

    def render(self, text):
        audio = tts.kokoro_audio(self.pipeline, text, self.voice, self.speed)
        audio = np.concatenate([audio, np.zeros(int(tts.SAMPLE_RATE * 0.4), dtype=np.float32)])  # cola de reverb
        return self.fx(audio[None, :], tts.SAMPLE_RATE)[0]

    def _add(self, n):
        with self.lock:
            self.pending += n
            if self.pending == 0:
                self.last_end = time.time()

    def say(self, text):
        self._add(1)
        self.texts.put(text)

    def play_filler(self, text, audio, at):
        """Frase de relleno ya sintetizada que suena en el instante `at` (time.time()).

        Se encola ya, asi la respuesta (que va detras en la cola) nunca suena antes que el relleno.
        Devuelve un token: cancel(token) la anula si al final no habia nada que responder.
        """
        token = {"cancel": False}
        self._add(1)
        self.audio.put((text, audio, at, token))
        return token

    @staticmethod
    def cancel(token):
        token["cancel"] = True

    def busy(self):
        return self.pending > 0

    def wait(self):
        while self.busy():
            time.sleep(0.05)

    def _synth_loop(self):
        while True:
            text = self.texts.get()
            try:
                self.audio.put((text, self.render(text), None, None))
            except Exception as e:
                log("voz", f"error sintetizando: {type(e).__name__}: {e}")
                self._add(-1)

    def _play_loop(self):
        import sounddevice as sd
        while True:
            text, audio, at, token = self.audio.get()
            try:
                if token is not None:  # relleno: espera a su hora, salvo que se cancele
                    while time.time() < at and not token["cancel"]:
                        time.sleep(0.02)
                    if token["cancel"]:
                        self._add(-1)
                        continue
                    log("relleno", text)
                else:
                    if self.on_first_audio:
                        self.on_first_audio(text)
                    log("calavera", text)
                sd.play(audio, tts.SAMPLE_RATE)
                sd.wait()
            except Exception as e:
                log("voz", f"error reproduciendo: {type(e).__name__}: {e}")
            self._add(-1)


class Ear:
    """Microfono + Silero VAD: devuelve el audio de una frase completa (se corta tras ~0.6 s de silencio)."""

    def __init__(self, device, voice):
        import sounddevice as sd
        from silero_vad import VADIterator, load_silero_vad
        self.voice = voice
        self.vad = VADIterator(load_silero_vad(), threshold=0.5, sampling_rate=MIC_SR,
                               min_silence_duration_ms=600, speech_pad_ms=200)
        self.blocks = queue.Queue()
        self.stream = sd.InputStream(samplerate=MIC_SR, channels=1, dtype="float32", blocksize=BLOCK,
                                     device=device, callback=lambda data, *_: self.blocks.put(data[:, 0].copy()))
        self.stream.start()

    def listen(self):
        import torch
        pre = collections.deque(maxlen=10)  # ~0.3 s antes de que el VAD reaccione: no se pierde la 1a silaba
        buf = None
        while True:
            block = self.blocks.get()
            if self.voice.busy() or time.time() - self.voice.last_end < 0.4:
                # la calavera esta hablando (o acaba de terminar): se ignora para no oirse a si misma
                self.vad.reset_states()
                pre.clear()
                buf = None
                continue
            event = self.vad(torch.from_numpy(block))
            if buf is None:
                pre.append(block)
                if event and "start" in event:
                    buf = list(pre)
                continue
            buf.append(block)
            if (event and "end" in event) or len(buf) * BLOCK > MAX_UTTERANCE_S * MIC_SR:
                self.vad.reset_states()
                audio = np.concatenate(buf)
                buf = None
                if len(audio) > 0.5 * MIC_SR:
                    return audio


class Stt:
    def __init__(self, size="base", device="cpu"):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(size, device=device, compute_type="int8" if device == "cpu" else "float16")

    def __call__(self, audio):
        segments, info = self.model.transcribe(audio, beam_size=1, condition_on_previous_text=False)
        lang = info.language
        if lang not in ("en", "es"):  # solo esperamos espanol o ingles: se repite con el mas probable de los dos
            probs = dict(info.all_language_probs or [])
            lang = "es" if probs.get("es", 0) > probs.get("en", 0) else "en"
            segments, info = self.model.transcribe(audio, beam_size=1, language=lang, condition_on_previous_text=False)
        text = " ".join(s.text.strip() for s in segments if s.no_speech_prob < 0.6).strip()
        if text.lower() in HALLUCINATIONS or len(text) < 2:
            return "", lang
        return text, lang


SENTENCE_END = re.compile(r"(?<!\.)[.!?](?!\.)[\"')\]]*\s+")  # fin de frase, pero no los "..."
MOOD_TAG = re.compile(r"\{\s*([a-zA-Z]+)\s*\}")


PUNCT = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "—": ", ", "–": ", ",
                       "…": "..."})


def clean(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"\*[^*]*\*|\([^)]*\)", "", text)  # *acciones* y (acotaciones)
    text = unicodedata.normalize("NFKD", text.translate(PUNCT))
    text = text.encode("ascii", "ignore").decode()  # quita acentos sueltos y emojis
    text = re.sub(r"\s+([,.!?])", r"\1", re.sub(r"\s+", " ", text))
    text = re.sub(r",+([.!?])", r"\1", text).strip(" ,")  # "Oh, 🎃!" -> "Oh!"
    return text if re.search(r"[A-Za-z]", text) else ""


class Brain:
    def __init__(self, model=DEFAULT_MODEL, persona=None, memory=None, max_turns=10):
        import ollama
        self.client, self.model, self.max_turns = ollama.Client(), model, max_turns
        self.persona = persona or personas.load(personas.DEFAULT_PERSONA)
        self.memory = memory  # memory.Memory o None
        self.memory_thread = None
        self.history = []
        self.turns = 0         # turnos desde que arranco: decide la etapa de la personalidad (personas.py)
        self.last_turn = 0.0

    def warm_up(self):
        """Carga el modelo en memoria antes del primer turno (si no, la 1a respuesta tarda mucho mas)."""
        self.client.generate(model=self.model, prompt="", keep_alive="30m")

    def reply(self, user_text, lang, on_mood=None):
        """Generador: va devolviendo frases completas de la respuesta mientras el LLM escribe."""
        if time.time() - self.last_turn > FORGET_AFTER_S:
            self.history = []  # mucho rato sin hablar: probablemente es otro visitante
        note = " (The visitor spoke Spanish.)" if lang == "es" else ""
        system = personas.system_prompt(self.persona, self.turns)
        if self.memory:
            system += self.memory.prompt_block()
        messages = ([{"role": "system", "content": system}] + self.history[-2 * self.max_turns:]
                    + [{"role": "user", "content": user_text + note}])
        kwargs = dict(model=self.model, messages=messages, stream=True, keep_alive="30m",
                      options={"temperature": 0.8, "num_predict": 150})
        try:
            stream = self.client.chat(think=False, **kwargs)
        except TypeError:  # cliente de ollama viejo, sin `think`: queda el /no_think del prompt
            stream = self.client.chat(**kwargs)
        full, buf, mood_done, said, first_cut = "", "", False, 0, False
        for chunk in stream:
            if said >= MAX_SENTENCES:  # el modelo se alarga: se corta aqui y no se espera al resto
                buf = ""
                break
            piece = chunk["message"]["content"]
            full += piece
            buf += piece
            if not mood_done:
                m = MOOD_TAG.search(buf)
                if m:
                    if on_mood and m.group(1).lower() in MOODS:
                        on_mood(m.group(1).lower())
                    buf = buf[:m.start()] + buf[m.end():]
                    mood_done = True
                elif len(buf) < 25 and "{" in buf:
                    continue  # la etiqueta aun se esta escribiendo
                else:
                    mood_done = True
            if not first_cut and said == 0:
                # primer trozo hasta la primera coma: se sintetiza en ~1 s y la respuesta empieza antes
                comma, end = re.search(r",\s+", buf), SENTENCE_END.search(buf)
                if comma and comma.start() >= 12 and (end is None or comma.start() < end.start()):
                    first_cut = True
                    if (head := clean(MOOD_TAG.sub("", buf[:comma.start() + 1]))):
                        yield head
                    buf = buf[comma.end():]
            while (m := SENTENCE_END.search(buf)):
                sentence, buf = clean(MOOD_TAG.sub("", buf[:m.end()])), buf[m.end():]
                if sentence and said < MAX_SENTENCES:
                    said += 1
                    yield sentence
        if said < MAX_SENTENCES and (rest := clean(MOOD_TAG.sub("", buf))):
            yield rest
        self.history += [{"role": "user", "content": user_text + note},
                         {"role": "assistant", "content": clean(full)}]
        self.turns += 1
        self.last_turn = time.time()
        if self.memory:  # en segundo plano, mientras la calavera habla: que hechos vale la pena recordar
            self.memory_thread = threading.Thread(target=self._remember, daemon=True,
                                                  args=(user_text, clean(MOOD_TAG.sub("", full))))
            self.memory_thread.start()

    def _remember(self, user_text, skull_text):
        try:
            for fact in self.memory.extract(self.client, self.model, user_text, skull_text):
                log("memoria", f"+ {fact}")
        except Exception as e:
            log("memoria", f"error: {type(e).__name__}: {e}")


class Eyes:
    """Opcional: manda el mood a los ojos (firmware/eyes, serie 115200, `M <mood>`)."""

    def __init__(self, port):
        import serial
        self.port = serial.Serial(port, 115200, timeout=0.2)
        time.sleep(2)  # el ESP32 se reinicia al abrir el puerto

    def mood(self, mood):
        self.port.write(f"M {mood}\n".encode())


def main():
    ap = argparse.ArgumentParser(description="Agente de voz de la calavera.")
    ap.add_argument("--mic", type=int, default=None, help="indice del microfono (--list-devices)")
    ap.add_argument("--list-devices", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="modelo de Ollama (qwen3:4b-instruct, llama3.2:3b...)")
    ap.add_argument("--whisper", default="base", help="tiny, base, small...")
    ap.add_argument("--whisper-device", default="cpu", help="cpu o cuda")
    ap.add_argument("--eyes", help="puerto serie del ESP32 de los ojos (p. ej. COM7 o /dev/ttyUSB0)")
    ap.add_argument("--persona", default=personas.DEFAULT_PERSONA,
                    help=f"{', '.join(personas.PERSONAS)} o un archivo .txt con tu propio prompt")
    ap.add_argument("--text", action="append", help="turno escrito, sin microfono (se puede repetir)")
    ap.add_argument("--no-intro", action="store_true")
    ap.add_argument("--memory", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "skull_memory.json"),
                    help="archivo de la memoria a largo plazo")
    ap.add_argument("--no-memory", action="store_true", help="sin memoria a largo plazo")
    ap.add_argument("--reset-memory", action="store_true", help="borra la memoria antes de empezar")
    args = ap.parse_args()
    persona = personas.load(args.persona)

    if args.list_devices:
        import sounddevice as sd
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                print(f"{i:3d}  {d['name']}  ({sd.query_hostapis(d['hostapi'])['name']})")
        print("por defecto:", sd.default.device[0])
        return

    # Una sola calavera a la vez: dos agentes abiertos se oyen entre si y hablan encima uno del otro.
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
    except OSError:
        print("Ya hay otro voice_agent.py corriendo (cierralo antes con Ctrl+C): no se abre un segundo.")
        return

    eyes = Eyes(args.eyes) if args.eyes else None
    set_mood = eyes.mood if eyes else (lambda m: log("ojos", m))

    log("inicio", "cargando voz...")
    voice = Voice()
    log("inicio", "pre-sintetizando frases de relleno...")
    fillers = [(f, voice.render(f)) for f in persona["fillers"]]
    recent = collections.deque(maxlen=max(0, len(fillers) // 2))

    def pick_filler():
        """Relleno al azar sin repetir los ultimos usados."""
        choice = random.choice([f for f in fillers if f[0] not in recent] or fillers)
        recent.append(choice[0])
        return choice
    log("inicio", f"cargando LLM {args.model} en Ollama (personalidad: {persona['name']})...")
    mem = None
    if not args.no_memory:
        mem = memory.Memory(args.memory)
        if args.reset_memory:
            mem.clear()
        log("memoria", f"{len(mem.facts)} recuerdos en {os.path.basename(args.memory)}")
    brain = Brain(args.model, persona, mem)
    brain.warm_up()

    timing = {}

    def first_audio(_text):
        if "t_end" in timing and "t_first" not in timing:
            timing["t_first"] = time.time()

    voice.on_first_audio = first_audio

    def turn(text, lang, t_end):
        """t_end: cuando termino de hablar el visitante (de ahi se miden los tiempos)."""
        timing.clear()
        timing["t_end"] = t_end
        set_mood("suspicious")
        t_llm = None
        for sentence in brain.reply(text, lang, on_mood=set_mood):
            if t_llm is None:
                t_llm = time.time() - timing["t_end"]
            voice.say(sentence)
        voice.wait()
        if "t_first" in timing:
            log("tiempos", f"LLM 1a frase a los {t_llm:.1f} s | respuesta sonando a los "
                           f"{timing['t_first'] - timing['t_end']:.1f} s (desde que dejaste de hablar)")
        set_mood("evil")

    if not args.no_intro:
        set_mood("possessed")
        voice.say(persona["intro"])
        voice.wait()
        set_mood("evil")

    if args.text:
        for text in args.text:
            log("tu", text)
            t_end = time.time()
            voice.play_filler(*pick_filler(), at=t_end + FILLER_DELAY_S)
            turn(text, "es" if re.search(r"[áéíóúñ¿¡]|\b(hola|quien|que|eres)\b", text.lower()) else "en", t_end)
        if brain.memory_thread:
            brain.memory_thread.join()  # que se guarde el ultimo recuerdo antes de salir
        return

    log("inicio", f"cargando Whisper {args.whisper}...")
    stt = Stt(args.whisper, args.whisper_device)
    ear = Ear(args.mic, voice)
    log("listo", "Habla cuando quieras (Ctrl+C para salir).")
    try:
        while True:
            audio = ear.listen()
            t_end = time.time()
            # el relleno se programa ya (suena FILLER_DELAY_S despues de que dejaste de hablar) y Whisper
            # trabaja mientras tanto; si no habia palabras (ruido), se cancela
            filler = voice.play_filler(*pick_filler(), at=t_end + FILLER_DELAY_S)
            text, lang = stt(audio)
            if not text:
                voice.cancel(filler)
                continue
            log(f"tu/{lang}", f"{text}   (Whisper {time.time() - t_end:.1f} s, audio {len(audio) / MIC_SR:.1f} s)")
            turn(text, lang, t_end)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
