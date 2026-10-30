"""Musica de fondo de Halloween generada por codigo (sin archivos ni derechos de autor).

Loop de 24 s sin cortes: zumbido grave con batido lento, caja de musica en La menor armonica, campanadas
lejanas y viento. Todo es periodico en 24 s, asi que al repetirse no se oye el salto.

  .venv/bin/python music.py                # lo reproduce en bucle (Ctrl+C para parar)
  .venv/bin/python music.py --save x.wav   # lo guarda en un WAV
  .venv/bin/python music.py --sting        # el golpe de terror de la ruleta, una vez
"""
import random
import sys

import numpy as np

SECONDS = 24.0
# La menor armonica (A B C D E F G#) desde La4
SCALE = [440.0, 493.88, 523.25, 587.33, 659.25, 698.46, 830.61, 880.0, 987.77, 1046.5]


def _bell(sr, freq, dur):
    t = np.arange(int(sr * dur)) / sr
    env = np.exp(-t * 1.3) * (1 - np.exp(-t * 250))
    tone = (np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * 2.76 * freq * t) * np.exp(-t * 2.5)
            + 0.3 * np.sin(2 * np.pi * 5.4 * freq * t) * np.exp(-t * 4.0))
    return tone * env


def _add_circular(buf, start, sig):
    """Suma `sig` en `buf` desde `start` dando la vuelta al final: la cola de las notas cae al inicio del loop."""
    idx = (start + np.arange(len(sig))) % len(buf)
    np.add.at(buf, idx, sig)


def make_loop(sr=22050, channels=1, seed=31):
    """Devuelve un array int16 (n,) o (n, 2) listo para pygame.sndarray.make_sound."""
    n = int(sr * SECONDS)
    t = np.arange(n) / sr
    rng = np.random.default_rng(seed)

    # zumbido: frecuencias redondeadas a ciclos enteros por loop; un oscilador desafinado 1/24 Hz crea el batido
    drone = np.zeros(n)
    for f, amp in ((55.0, 1.0), (82.41, 0.6), (110.0, 0.35)):
        fq = round(f * SECONDS) / SECONDS
        drone += amp * np.sin(2 * np.pi * fq * t)
    drone += 0.8 * np.sin(2 * np.pi * ((round(55.0 * SECONDS) + 1) / SECONDS) * t)
    drone *= 1 + 0.25 * np.sin(2 * np.pi * (2 / SECONDS) * t)
    drone /= np.abs(drone).max()

    # caja de musica: caminata por la escala con silencios
    bells = np.zeros(n)
    r, pos, beat = random.Random(seed), 0, 0.75
    for k in range(int(SECONDS / beat)):
        if r.random() < 0.3 and k:
            continue
        pos = min(len(SCALE) - 1, max(0, pos + r.choice([-2, -1, -1, 1, 1, 2])))
        _add_circular(bells, int(k * beat * sr), _bell(sr, SCALE[pos], 3.5) * r.uniform(0.6, 1.0))
    bells /= np.abs(bells).max()

    # campanadas graves lejanas
    toll = np.zeros(n)
    for when in (0.0, 12.0):
        _add_circular(toll, int(when * sr), _bell(sr, 164.81, 8.0))
    toll /= np.abs(toll).max()

    # viento: ruido filtrado en frecuencia (la FFT inversa es periodica) con oleadas lentas
    spec = np.fft.rfft(rng.standard_normal(n))
    spec *= np.exp(-np.fft.rfftfreq(n, 1 / sr) / 600)
    wind = np.fft.irfft(spec, n)
    wind = wind / np.abs(wind).max() * (0.5 + 0.5 * np.sin(2 * np.pi * (3 / SECONDS) * t + 1.0)) ** 2

    mix = 0.35 * drone + 0.55 * bells + 0.30 * toll + 0.30 * wind
    mix = mix / np.abs(mix).max() * 0.9
    if channels == 2:  # un poco de anchura estereo: el canal derecho va 12 ms despues (el roll mantiene el loop)
        mix = np.column_stack((mix, np.roll(mix, int(sr * 0.012))))
    return np.ascontiguousarray((mix * 32767).astype(np.int16))


def loop_from_file(path, crossfade=1.0, silence=0.02):
    """Carga un mp3/ogg/wav como loop continuo para pygame: recorta el silencio del inicio y del final y funde
    el final con el principio (crossfade) para que no haya hueco ni salto al repetirse."""
    import pygame

    sound = pygame.mixer.Sound(path)
    arr = pygame.sndarray.array(sound).astype(np.float32)  # ya convertido al formato del mezclador
    level = np.abs(arr).max(axis=1) if arr.ndim == 2 else np.abs(arr)
    loud = np.where(level > silence * 32767)[0]
    arr = arr[loud[0]:loud[-1] + 1]
    fade = min(int(pygame.mixer.get_init()[0] * crossfade), len(arr) // 3)
    up = np.linspace(0, 1, fade, dtype=np.float32)
    up = up[:, None] if arr.ndim == 2 else up
    loop = arr[:-fade].copy()
    loop[:fade] = arr[:fade] * up + arr[-fade:] * (1 - up)
    print(f"[musica] {path}: {len(arr) / pygame.mixer.get_init()[0]:.1f} s utiles, loop de {len(loop) / pygame.mixer.get_init()[0]:.1f} s")
    return pygame.sndarray.make_sound(np.ascontiguousarray(loop.astype(np.int16)))


def make_sting(sr=22050, channels=1, seed=7):
    """Golpe de terror de ~3.5 s para el resultado de la ruleta: impacto grave, chillido disonante que sube
    (tres voces: tono, tritono y segunda menor) y una campana lugubre al final."""
    dur = 3.5
    n = int(sr * dur)
    t = np.arange(n) / sr
    rng = np.random.default_rng(seed)

    f = 30 + 70 * np.exp(-t * 4)  # el impacto cae de 100 a 30 Hz
    boom = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 2.2)
    boom += 0.6 * rng.standard_normal(n) * np.exp(-t * 14)

    glide = 520 + 730 * np.clip(t / 1.4, 0, 1) ** 1.5
    glide *= 1 + 0.012 * np.sin(2 * np.pi * 6.5 * t)  # vibrato nervioso
    screech = np.zeros(n)
    for ratio, amp in ((1.0, 1.0), (1.414, 0.6), (1.0595, 0.5)):
        phase = 2 * np.pi * np.cumsum(glide * ratio) / sr
        screech += amp * sum(np.sin(k * phase) / k for k in (1, 2, 3))
    screech *= np.minimum(t / 0.02, 1) * np.exp(-t * 1.1)

    tail = np.zeros(n)
    bell = _bell(sr, 82.41, 3.2)
    tail[int(sr * 0.3):int(sr * 0.3) + len(bell)] = bell[:n - int(sr * 0.3)]

    mix = boom / np.abs(boom).max() + 0.5 * screech / np.abs(screech).max() + 0.5 * tail / np.abs(tail).max()
    mix *= np.minimum((dur - t) / 0.4, 1)  # fundido final
    mix = mix / np.abs(mix).max() * 0.95
    if channels == 2:
        mix = np.column_stack((mix, np.roll(mix, int(sr * 0.012))))
    return np.ascontiguousarray((mix * 32767).astype(np.int16))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Reproduce el loop de Halloween (Ctrl+C para parar) o lo guarda.")
    ap.add_argument("--save", help="guardar en un WAV en vez de reproducir")
    ap.add_argument("--volume", type=float, default=0.5)
    ap.add_argument("--sting", action="store_true", help="suena una vez el golpe de terror de la ruleta")
    args = ap.parse_args()
    if args.sting:
        import sounddevice as sd
        sd.play((make_sting() * args.volume).astype(np.int16), 22050)
        sd.wait()
        sys.exit()
    loop = make_loop()
    if args.save:
        import soundfile as sf
        sf.write(args.save, loop, 22050)
        print("guardado", args.save)
    else:
        import sounddevice as sd
        print("Sonando el loop de 24 s... Ctrl+C para parar")
        try:
            while True:
                sd.play((loop * args.volume).astype(np.int16), 22050)
                sd.wait()
        except KeyboardInterrupt:
            sd.stop()
