#!/usr/bin/env python3
"""Mueve el hoverboard por el ESP32 del cuello (firmware/neck/neck.ino) repitiendo `V` a 20 Hz.

`V` caduca a los 300 ms en el firmware (proteccion), asi que hay que repetirlo.

Uso (SOLO con las ruedas en el aire o con el robot vigilado, la fuente limitada y el paro a mano):
  python3 tools/hover_drive.py 100 0 3          # velocidad 100, giro 0, durante 3 s, luego frena
  python3 tools/hover_drive.py 0 90 2           # gira sobre si mismo 2 s
  python3 tools/hover_drive.py --keys           # teclado: w/s velocidad, a/d giro, espacio frena, q sale

Cierra antes el monitor serie (el puerto solo admite un programa).
Si las placas estan apagadas, enciendelas antes con `E` (relés) o a mano.
Abre el puerto con DTR/RTS en bajo para no reiniciar el ESP32 por autoreset del CP2102.
"""
import argparse, sys, time
import serial

HZ = 20
MAX = 150          # igual que MAX_SPEED en neck.ino


def open_port(path):
    s = serial.Serial()
    s.port, s.baudrate, s.timeout = path, 115200, 0.02
    s.dtr = False
    s.rts = False
    s.open()
    time.sleep(0.3)
    s.reset_input_buffer()
    return s


def send(s, line):
    s.write((line + "\n").encode())


def drain(s, t=0.05):
    end = time.time() + t
    out = b""
    while time.time() < end:
        out += s.read(300)
    return out.decode(errors="replace")


def telem(s):
    send(s, "W")
    txt = drain(s, 0.25)
    return "\n".join(l for l in txt.splitlines() if l.startswith(("HOVER", "ESTADO", "FALLO")))


def run_timed(s, speed, steer, secs):
    t_end = time.time() + secs
    try:
        while time.time() < t_end:
            send(s, f"V {speed} {steer}")
            drain(s, 1.0 / HZ)
        print(telem(s))
    finally:
        send(s, "X")


def run_keys(s):
    import termios, tty, select
    speed = steer = 0
    step = 20
    print("w/s: velocidad +-%d  a/d: giro +-%d  espacio: frenar  q: salir" % (step, step))
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        last = 0
        while True:
            if select.select([sys.stdin], [], [], 1.0 / HZ)[0]:
                k = sys.stdin.read(1)
                if k == "q":
                    break
                if k == " ":
                    speed = steer = 0
                elif k == "w":
                    speed = min(MAX, speed + step)
                elif k == "s":
                    speed = max(-MAX, speed - step)
                elif k == "a":
                    steer = max(-MAX, steer - step)
                elif k == "d":
                    steer = min(MAX, steer + step)
                print(f"\rvel={speed:4d} giro={steer:4d}   ", end="", flush=True)
            send(s, f"V {speed} {steer}")
            drain(s, 0.0)
            if time.time() - last > 1.0:
                last = time.time()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        send(s, "X")
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("speed", nargs="?", type=int, default=0)
    ap.add_argument("steer", nargs="?", type=int, default=0)
    ap.add_argument("secs", nargs="?", type=float, default=2.0)
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--keys", action="store_true", help="modo teclado")
    ap.add_argument("--no-enable", action="store_true", help="no mandar H 1 / H 0")
    a = ap.parse_args()
    if abs(a.speed) > MAX or abs(a.steer) > MAX:
        sys.exit(f"velocidad y giro deben estar entre -{MAX} y {MAX}")
    s = open_port(a.port)
    try:
        if not a.no_enable:
            send(s, "H 1")
            print(drain(s, 0.4).strip())
        if a.keys:
            run_keys(s)
        else:
            run_timed(s, a.speed, a.steer, a.secs)
    finally:
        send(s, "X")
        if not a.no_enable:
            send(s, "H 0")
        drain(s, 0.2)
        s.close()


if __name__ == "__main__":
    main()
