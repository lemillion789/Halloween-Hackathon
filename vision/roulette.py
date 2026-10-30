"""Ruleta de la calavera: recorre a los participantes visibles, frena en uno y le manda un reto.

Se activa con la tecla S en person_costume.py --camera. Nemotron escribe el anuncio mientras gira.
"""
import random
import threading
import time

import cv2

from skull_lines import roulette_intro, write_roulette_line

ANNOUNCE_TIMEOUT = 8.0  # si la frase no llega a tiempo, se usa una de respaldo
SHOW_WINNER = 6.0       # segundos con el elegido resaltado


class Roulette:
    def __init__(self, people, speaker, model, dare):
        """people: lista de (id, dict del VLM) de quienes estan en pantalla."""
        self.people = dict(people)
        self.ids = list(self.people)
        self.speaker = speaker
        n = len(self.ids)
        winner = random.randrange(n)
        seq = [winner]
        for _ in range(random.randint(18, 24)):  # se arma hacia atras para que termine en el elegido
            seq.append((seq[-1] - 1) % n)
        self.seq = seq[::-1]
        self.delays = [0.07 + 0.5 * (i / len(self.seq)) ** 2 for i in range(len(self.seq))]  # frena poco a poco
        self.winner = self.ids[winner]
        self.i = 0
        self.next_at = time.time()
        self.finished_at = None
        self.line = None
        self.said = False
        threading.Thread(target=self._write, args=(model, dare), daemon=True).start()
        if speaker:
            speaker.say(roulette_intro())

    def _write(self, model, dare):
        self.line = write_roulette_line(self.people[self.winner], dare, model)

    @property
    def current(self):
        return self.ids[self.seq[self.i]]

    def update(self, now):
        """Avanza la ruleta; devuelve False cuando ya termino y hay que quitarla."""
        if self.finished_at is None:
            if now >= self.next_at:
                if self.i < len(self.seq) - 1:
                    self.i += 1
                    self.next_at = now + self.delays[self.i]
                else:
                    self.finished_at = now
            return True
        if not self.said and (self.line or now - self.finished_at > ANNOUNCE_TIMEOUT):
            self.said = True
            line = self.line or "The wheel has chosen. Take a shot, you know who you are."
            print(f'[ruleta] elegido #{self.winner}: "{line}"')
            if self.speaker:
                self.speaker.say(line)
        return now - self.finished_at < SHOW_WINNER

    def draw(self, frame, ids, boxes):
        done = self.finished_at is not None
        target = self.winner if done else self.current
        for tid, (x1, y1, x2, y2) in zip(ids, boxes):
            if tid != target:
                continue
            color = (0, 0, 255) if done else (0, 255, 255)
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 8 if done else 5)
            label = "CHOSEN!" if done else "..."
            cv2.putText(frame, label, (int(x1), max(40, int(y1) - 20)), cv2.FONT_HERSHEY_SIMPLEX, 1.4, color, 4)
