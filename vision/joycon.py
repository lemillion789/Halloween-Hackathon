"""Botones de un Joy-Con (R) por evdev, sin dependencias.

pygame/SDL no detecta el Joy-Con con el driver hid_nintendo, asi que se lee directo de
/dev/input/event*. Si el Joy-Con no esta conectado, `pressed()` devuelve siempre False y se
reintenta cada 2 s (sirve tambien al reconectar). Solo Linux; en otros sistemas no hace nada.
Codigos: A=305 (BTN_EAST), B=304, X=307, Y=308 (probados con el Joy-Con R); PLUS=315 y HOME=316 (segun el driver, sin probar).
"""
import collections
import glob
import os
import struct
import threading
import time

BTN_A, BTN_B, BTN_X, BTN_Y, BTN_PLUS, BTN_HOME = 305, 304, 307, 308, 315, 316
_EVENT = struct.Struct("llHHi")   # sec, usec, type, code, value
_EV_KEY = 1


def find_event_node(name_part="Joy-Con"):
    """Ruta /dev/input/eventN del Joy-Con (ignora el dispositivo '(IMU)'), o None."""
    for path in glob.glob("/sys/class/input/input*/name"):
        try:
            name = open(path).read().strip()
        except OSError:
            continue
        if name_part in name and "IMU" not in name:
            for entry in os.listdir(os.path.dirname(path)):
                if entry.startswith("event"):
                    return "/dev/input/" + entry
    return None


class JoyCon:
    def __init__(self):
        self.connected = False
        self._queue = collections.deque(maxlen=32)   # codigos de boton, en orden de pulsacion
        self._lock = threading.Lock()
        if os.name == "posix":
            threading.Thread(target=self._run, daemon=True).start()

    def pressed(self, code=BTN_A):
        """True una vez por cada pulsacion de ese boton desde la ultima llamada."""
        with self._lock:
            if code in self._queue:
                self._queue.remove(code)
                return True
        return False

    def poll(self):
        """Todos los botones pulsados desde la ultima llamada, en orden."""
        with self._lock:
            codes = list(self._queue)
            self._queue.clear()
        return codes

    def _run(self):
        while True:
            node = find_event_node()
            try:
                fd = os.open(node, os.O_RDONLY) if node else None
            except OSError:
                fd = None
            if fd is None:
                time.sleep(2)
                continue
            self.connected = True
            try:
                while True:
                    data = os.read(fd, _EVENT.size * 16)
                    for i in range(0, len(data) - _EVENT.size + 1, _EVENT.size):
                        _, _, typ, code, val = _EVENT.unpack_from(data, i)
                        if typ == _EV_KEY and val == 1:
                            with self._lock:
                                self._queue.append(code)
            except OSError:   # se desconecto
                pass
            finally:
                self.connected = False
                os.close(fd)
            time.sleep(1)


if __name__ == "__main__":   # prueba: pulsa A, Ctrl+C sale
    jc = JoyCon()
    print("Pulsa botones del Joy-Con (A, B, X, Y, +, HOME)...")
    while True:
        for c in jc.poll():
            print("boton", c)
        time.sleep(0.02)
