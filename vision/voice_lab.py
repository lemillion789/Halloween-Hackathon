"""Laboratorio de voces de la calavera: escribe frases y escuchalas con distintos estilos.

Uso (Windows):  .venv/Scripts/python voice_lab.py [--style evil_ai] [--voice bm_george]
Uso (Linux):    .venv/bin/python voice_lab.py
Abre una ventana (caja de texto, estilo, voz, deslizadores del efecto, Hablar / Comparar / Guardar).

Con --cli funciona en el terminal: escribe una frase y Enter. Comandos (empiezan con /):
  /style monster | evil_ai | spooky | dry   cambiar estilo (dry = sin efectos)
  /voice am_onyx                  cambiar voz de Kokoro (/voices = sugerencias)
  /speed 0.8                      velocidad (<1 = mas lento)
  /pitch -4 | /pitch default      tono en semitonos
  /k EVIL_RING_MIX 0.5            cambiar un ajuste del estilo (/status muestra los actuales)
  /k MONSTER_GROWL 0.5            (sin valor: /k lista los nombres)
  /all                            repetir la ultima frase en todos los estilos
  /r                              repetir la ultima frase
  /save nombre                    guardar la ultima frase en voice_lab_out/nombre.wav
  /status   /help   /q
"""
import argparse
import os
import sys

os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

import numpy as np

import tts

VOICES = {
    "bm_george": "britanico grave",
    "bm_lewis": "britanico, mas oscuro",
    "bm_fable": "britanico, narrador",
    "am_onyx": "americano muy grave",
    "am_fenrir": "americano grave, rasposo",
    "am_michael": "americano (por defecto, con monster)",
    "af_bella": "femenina americana (fantasma?)",
    "bf_emma": "femenina britanica",
}
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_lab_out")


class Lab:
    def __init__(self, style, voice, speed, pitch):
        self.style, self.voice, self.speed, self.pitch = style, voice, speed, pitch
        self.pipelines = {}
        self.fx = None
        self.last_text, self.last_audio = None, None
        self.rebuild()

    def rebuild(self):
        if self.style == "dry":
            self.fx = None
            return
        make_fx, default_pitch = tts.STYLES[self.style]
        self.fx = make_fx(default_pitch if self.pitch is None else self.pitch)

    def raw(self, text):
        from kokoro import KPipeline
        lang = self.voice[0]
        if lang not in self.pipelines:
            print("[cargando Kokoro...]", flush=True)
            self.pipelines[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
        audio = tts.kokoro_audio(self.pipelines[lang], text, self.voice, self.speed)
        return np.concatenate([audio, np.zeros(int(tts.SAMPLE_RATE * 0.8), dtype=np.float32)])

    def render(self, text):
        audio = self.raw(text)
        if self.fx is not None:
            audio = self.fx(audio[None, :], tts.SAMPLE_RATE)[0]
        self.last_text, self.last_audio = text, audio
        return audio

    @staticmethod
    def play(audio):
        import sounddevice as sd
        sd.play(audio, tts.SAMPLE_RATE)
        sd.wait()

    def status(self):
        pitch = "default" if self.pitch is None else f"{self.pitch:+g}"
        s = f"estilo={self.style} voz={self.voice} speed={self.speed} pitch={pitch}"
        knobs = tts.STYLE_KNOBS.get(self.style, [])
        if knobs:
            s += " | " + " ".join(f"{n}={getattr(tts, n):g}" for n, *_ in knobs)
        print(s)

    def command(self, line):
        cmd, _, arg = line[1:].partition(" ")
        arg = arg.strip()
        if cmd in ("q", "quit", "exit"):
            sys.exit(0)
        elif cmd == "help":
            print(__doc__)
        elif cmd == "status":
            self.status()
        elif cmd == "voices":
            for v, d in VOICES.items():
                print(f"  {v:11s} {d}")
            print("  lista completa: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md")
        elif cmd == "style":
            if arg not in list(tts.STYLES) + ["dry"]:
                print("estilos:", ", ".join(list(tts.STYLES) + ["dry"]))
                return
            self.style = arg
            self.rebuild()
            self.status()
        elif cmd == "voice" and arg:
            self.voice = arg
            self.status()
        elif cmd == "speed" and arg:
            self.speed = float(arg)
            self.status()
        elif cmd == "pitch" and arg:
            self.pitch = None if arg == "default" else float(arg)
            self.rebuild()
            self.status()
        elif cmd == "k":
            name, _, value = arg.partition(" ")
            allowed = [n for spec in tts.STYLE_KNOBS.values() for n, *_ in spec]
            if name not in allowed or not value:
                print("uso: /k NOMBRE valor   nombres:", ", ".join(allowed))
                return
            setattr(tts, name, float(value))
            self.rebuild()
            self.status()
        elif cmd == "r":
            if self.last_text:
                self.play(self.render(self.last_text))
        elif cmd == "all":
            if not self.last_text:
                print("primero escribe una frase")
                return
            current = self.style
            for st in ["dry"] + list(tts.STYLES):
                self.style = st
                self.rebuild()
                print(f"[{st}]", flush=True)
                self.play(self.render(self.last_text))
            self.style = current
            self.rebuild()
        elif cmd == "save":
            if self.last_audio is None:
                print("nada que guardar todavia")
                return
            import soundfile as sf
            os.makedirs(OUT_DIR, exist_ok=True)
            name = arg or f"{self.style}_{len(os.listdir(OUT_DIR)) + 1:02d}"
            path = os.path.join(OUT_DIR, name if name.endswith(".wav") else name + ".wav")
            sf.write(path, self.last_audio, tts.SAMPLE_RATE)
            print("guardado", path)
        else:
            print("comando desconocido; /help")


def gui(lab):
    """Ventana (tkinter): no depende de que el terminal deje escribir."""
    import queue
    import threading
    import tkinter as tk
    from tkinter import filedialog, ttk

    root = tk.Tk()
    root.title("Laboratorio de voces - calavera")
    root.geometry("640x600")
    pad = {"padx": 8, "pady": 4}

    ttk.Label(root, text="Frase (Enter = hablar, Shift+Enter = salto de linea). Pausas: [p] = 0.8 s, [p2] = 2 s").pack(anchor="w", **pad)
    text = tk.Text(root, height=4, wrap="word", font=("Segoe UI", 11))
    text.pack(fill="x", **pad)
    text.insert("1.0", "What is this? [p1.5] What am I? [p2] Who... are you?")

    form = ttk.Frame(root)
    form.pack(fill="x", **pad)
    style_v = tk.StringVar(value=lab.style)
    voice_v = tk.StringVar(value=lab.voice)
    speed_v = tk.DoubleVar(value=lab.speed)
    pitch_v = tk.StringVar(value="" if lab.pitch is None else str(lab.pitch))
    ttk.Label(form, text="Estilo").grid(row=0, column=0, sticky="w")
    ttk.Combobox(form, textvariable=style_v, values=list(tts.STYLES) + ["dry"], state="readonly", width=12).grid(row=0, column=1, sticky="w")
    ttk.Label(form, text="Voz").grid(row=0, column=2, sticky="w", padx=(16, 0))
    ttk.Combobox(form, textvariable=voice_v, values=list(VOICES), width=12).grid(row=0, column=3, sticky="w")
    ttk.Label(form, text="Velocidad").grid(row=1, column=0, sticky="w")
    ttk.Spinbox(form, textvariable=speed_v, from_=0.5, to=1.5, increment=0.05, width=6).grid(row=1, column=1, sticky="w")
    ttk.Label(form, text="Tono (semitonos, vacio = del estilo)").grid(row=1, column=2, sticky="w", padx=(16, 0))
    ttk.Entry(form, textvariable=pitch_v, width=6).grid(row=1, column=3, sticky="w")

    sliders = ttk.LabelFrame(root, text="Ajustes del estilo")
    sliders.pack(fill="x", **pad)
    knobs = {}  # variable de tts -> DoubleVar (solo las del estilo elegido)

    def build_sliders(*_):
        for w in sliders.winfo_children():
            w.destroy()
        knobs.clear()
        spec = tts.STYLE_KNOBS.get(style_v.get(), [])
        sliders.config(text=f"Ajustes de {style_v.get()}" if spec else "Este estilo no tiene ajustes")
        for row, (name, label, lo, hi) in enumerate(spec):
            var = tk.DoubleVar(value=getattr(tts, name))
            ttk.Label(sliders, text=label, width=24).grid(row=row, column=0, sticky="w", padx=6)
            ttk.Scale(sliders, variable=var, from_=lo, to=hi, length=300).grid(row=row, column=1, padx=6)
            val = ttk.Label(sliders, width=6)
            val.grid(row=row, column=2)
            var.trace_add("write", lambda *_, v=var, l=val: l.config(text=f"{v.get():.2f}"))
            val.config(text=f"{var.get():.2f}")
            knobs[name] = var

    style_v.trace_add("write", build_sliders)
    build_sliders()

    status = tk.StringVar(value="Listo. La primera frase tarda unos segundos (carga Kokoro).")
    jobs, results = queue.Queue(), queue.Queue()

    def apply():
        lab.style, lab.voice, lab.speed = style_v.get(), voice_v.get().strip(), float(speed_v.get())
        p = pitch_v.get().strip()
        lab.pitch = float(p) if p else None
        for name, var in knobs.items():
            setattr(tts, name, float(var.get()))
        lab.rebuild()

    def worker():
        while True:
            kind, arg = jobs.get()
            try:
                if kind == "say":
                    results.put(f'Hablando ({lab.style}, {lab.voice})...')
                    lab.play(lab.render(arg))
                elif kind == "all":
                    current = lab.style
                    for st in ["dry"] + list(tts.STYLES):
                        lab.style = st
                        lab.rebuild()
                        results.put(f"Comparando: {st}")
                        lab.play(lab.render(arg))
                    lab.style = current
                    lab.rebuild()
                results.put("Listo.")
            except Exception as e:
                results.put(f"Error: {type(e).__name__}: {e}")

    threading.Thread(target=worker, daemon=True).start()

    def poll():
        while not results.empty():
            status.set(results.get())
        root.after(100, poll)

    def phrase():
        return text.get("1.0", "end").strip()

    def say(*_):
        if phrase():
            try:
                apply()
            except ValueError as e:
                status.set(f"Valor no valido: {e}")
                return "break"
            jobs.put(("say", phrase()))
        return "break"  # que Enter no meta un salto de linea

    def compare():
        if phrase():
            apply()
            jobs.put(("all", phrase()))

    def save():
        if lab.last_audio is None:
            status.set("Primero haz hablar una frase.")
            return
        import soundfile as sf
        os.makedirs(OUT_DIR, exist_ok=True)
        path = filedialog.asksaveasfilename(initialdir=OUT_DIR, defaultextension=".wav",
                                            initialfile=f"{lab.style}_{len(os.listdir(OUT_DIR)) + 1:02d}.wav",
                                            filetypes=[("WAV", "*.wav")])
        if path:
            sf.write(path, lab.last_audio, tts.SAMPLE_RATE)
            status.set(f"Guardado: {path}")

    buttons = ttk.Frame(root)
    buttons.pack(fill="x", **pad)
    ttk.Button(buttons, text="Hablar  (Enter)", command=say).pack(side="left")
    ttk.Button(buttons, text="Comparar estilos", command=compare).pack(side="left", padx=6)
    ttk.Button(buttons, text="Guardar ultima WAV", command=save).pack(side="left")
    ttk.Label(root, textvariable=status, foreground="#a00").pack(anchor="w", **pad)
    ttk.Label(root, text="Mas voces: /voices en modo --cli o huggingface.co/hexgrad/Kokoro-82M (VOICES.md)",
              foreground="#666").pack(anchor="w", **pad)

    text.bind("<Return>", say)
    text.bind("<Shift-Return>", lambda e: None)  # salto de linea normal
    text.focus_set()
    poll()
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="Escribe frases y escuchalas con la voz de la calavera.")
    ap.add_argument("--style", default=tts.STYLE, choices=list(tts.STYLES) + ["dry"])
    ap.add_argument("--voice", default=tts.VOICE)
    ap.add_argument("--speed", type=float, default=tts.SPEED)
    ap.add_argument("--pitch", type=float, default=None)
    ap.add_argument("--cli", action="store_true", help="modo texto en el terminal en vez de ventana")
    args = ap.parse_args()

    lab = Lab(args.style, args.voice, args.speed, args.pitch)
    if not args.cli:
        gui(lab)
        return
    print("Laboratorio de voces. Escribe una frase y Enter; /help para comandos, /q para salir.")
    lab.status()
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        try:
            if line.startswith("/"):
                lab.command(line)
            else:
                lab.play(lab.render(line))
        except SystemExit:
            break
        except Exception as e:  # una frase rara o un valor mal escrito no debe cerrar el programa
            print(f"error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
