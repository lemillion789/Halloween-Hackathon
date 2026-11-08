#!/usr/bin/env python3
"""Prueba de bancada de la placa del hoverboard a traves del ESP32 del cuello (firmware/neck/neck.ino).

SOLO con la rueda en el aire, fuente limitada y las manos lejos. Ctrl+C la detiene.

Uso:
  python3 Hoverboard/test_uart.py /dev/ttyUSB0            # rampa suave 0 -> +MAX -> 0 -> -MAX -> 0
  python3 Hoverboard/test_uart.py /dev/ttyUSB0 --max 40   # velocidad maxima de la prueba (unidades del neck, tope 150)
  python3 Hoverboard/test_uart.py /dev/ttyUSB0 --hold 40  # mantiene 40 hasta Ctrl+C

El ESP32 expira la orden a los 300 ms, asi que este script la reenvia a 20 Hz.
Si el script o el cable se cae, la rueda se detiene sola (el ESP32 deja de mandar tramas y
la placa deshabilita el motor a los 500 ms).
"""
import argparse
import sys
import time

import serial

HARD_LIMIT = 150          # igual que MAX_SPEED en neck.ino
SEND_HZ = 20


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port")
    ap.add_argument("--max", type=int, default=40, help="velocidad maxima de la rampa (default 40)")
    ap.add_argument("--hold", type=int, default=None, help="mantener esta velocidad constante")
    ap.add_argument("--ramp", type=float, default=3.0, help="segundos por tramo de rampa (default 3)")
    args = ap.parse_args()

    top = max(0, min(abs(args.max), HARD_LIMIT))
    ser = serial.Serial(args.port, 115200, timeout=0.05)
    time.sleep(2.0)                      # el ESP32 se reinicia al abrir el puerto
    ser.reset_input_buffer()

    def send(line):
        ser.write((line + "\n").encode())

    def show():
        data = ser.read(ser.in_waiting or 1).decode(errors="replace").strip()
        if data:
            print("<-", data)

    def profile():
        """Genera (velocidad) en cada tick segun la rampa o el hold."""
        if args.hold is not None:
            while True:
                yield max(-HARD_LIMIT, min(args.hold, HARD_LIMIT))
        steps = int(args.ramp * SEND_HZ)
        for a, b in ((0, top), (top, 0), (0, -top), (-top, 0)):
            for i in range(steps):
                yield int(a + (b - a) * i / steps)
        yield 0

    print(f"Habilitando hoverboard (max {top}). Ctrl+C para parar.")
    send("H 1")
    try:
        for speed in profile():
            send(f"V {speed} 0")
            print(f"V {speed:4d} 0", end="\r", flush=True)
            show()
            time.sleep(1.0 / SEND_HZ)
    except KeyboardInterrupt:
        print("\nInterrumpido.")
    finally:
        for _ in range(5):
            send("V 0 0")
            send("X")
            time.sleep(0.05)
        send("H 0")
        time.sleep(0.2)
        show()
        ser.close()
        print("Parado y deshabilitado.")


if __name__ == "__main__":
    sys.exit(main())
