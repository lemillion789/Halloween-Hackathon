"""Modo juego de la calavera: foto -> separa a los personajes -> los describe -> ruleta didactica.

Pasos: 1) vista de camara, A (Joy-Con) toma la foto; 2) YOLO separa a las personas y cada una vuela a una
tarjeta; 3) el VLM describe cada tarjeta (giran al llegar el resultado) y la calavera las presenta de
izquierda a derecha; 4) tecla S: ruleta con la cara de cada participante, puntero y tictac; el elegido
sube al centro con su reto.

Uso:
  .venv/bin/python game.py --source test_images/gemini_2.jpeg   # imagen como si fuera la camara
  .venv/bin/python game.py --camera 0
  Pantalla completa por defecto: --display N elige el monitor, --windowed la quita.
  --mute  sin voz (solo subtitulos) | --dare "drink your whole glass" | --model ... | --speed 2  (acelera las animaciones)
Joy-Con R: A foto, X ruleta (otra vez para repetir), B nueva foto, Y musica on/off, + salir. (El teclado sigue valiendo:
ESPACIO, S, R, M, ESC.)
Musica: loop de Halloween generado por music.py (baja solo cuando la calavera habla); --music archivo.mp3 usa la tuya.
"""
import argparse
import math
import os
import random
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import pygame
from ultralytics import YOLO

from costume_describer import DEFAULT_MODEL, describe_hedged
from joycon import BTN_A, BTN_B, BTN_HOME, BTN_PLUS, BTN_X, BTN_Y, JoyCon
from person_costume import NO_COSTUME, crop_person
from skull_lines import (MORE_WAIT, ROULETTE_INTROS, all_waiting_lines, person_intro, roulette_intro, waiting_lines, write_line_named,
                         write_roulette_line)
from tts import Speaker

W, H = 1280, 720
JOY_KEYS = {BTN_A: pygame.K_SPACE, BTN_X: pygame.K_s, BTN_B: pygame.K_r, BTN_Y: pygame.K_m}   # Joy-Con R -> tecla
FPS = 60
WAIT_SPEED = 0.74     # las frases de espera van mas lentas que la voz normal (0.85)
PERSON_SPEED = 0.95   # al presentar y describir a cada persona la voz acelera un poco
WAIT_PAUSE = 2.0      # segundos de silencio entre frase y frase de espera
STING_DELAY = 1.6      # el anuncio de la ruleta espera a que pase lo mas fuerte del golpe de terror
MAX_WAIT_LINE = 8.0   # segundos esperando el anuncio de la ruleta antes de usar uno generico
SPIN_TIME = 7.0
PALETTE = [(255, 110, 0), (150, 70, 220), (50, 190, 100), (220, 40, 70), (240, 200, 40), (40, 150, 220)]
ORANGE, GREEN, RED, BONE = (255, 130, 20), (120, 255, 90), (230, 40, 50), (235, 230, 215)
CARD_BG, INK = (34, 20, 48), (14, 6, 22)
DEFAULT_MUSIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_sounds", "sound1.mp3")
# sellos que aparecen en la tarjeta cuando se identifica a alguien (en vez de la descripcion)
STAMPS = [["DONE!"], ["FOUND!"], ["WANTED", "500 SEK"], ["CAUGHT!"], ["BUSTED!"], ["GOTCHA!"], ["REWARD", "500 SEK"],
          ["SOUL", "LOGGED"], ["TAGGED!"], ["GUILTY!"], ["BOUNTY", "500 SEK"], ["NICE TRY"]]
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CATEGORY_COLORS = {"superhero": (60, 140, 255), "villain": (220, 40, 70), "undead": (150, 200, 150),
                   "monster": (120, 220, 80), "fantasy": (190, 100, 240), "movie/tv": (255, 170, 40),
                   "anime/game": (255, 100, 180), "none": (130, 130, 130)}


# ---------- utilidades ----------
def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def ease_out(t):
    return 1 - (1 - clamp(t)) ** 3


def ease_io(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_back(t):
    t = clamp(t)
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def clean(text):
    """El tipografo no tiene todos los simbolos (guiones raros, comillas curvas): se pasan a ASCII."""
    text = text.replace("‑", "-").replace("—", " - ").replace("–", "-")
    text = text.translate({0x2019: "'", 0x2018: "'", 0x201c: '"', 0x201d: '"'})
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def bgr_surface(img):
    h, w = img.shape[:2]
    return pygame.image.frombuffer(cv2.cvtColor(img, cv2.COLOR_BGR2RGB).tobytes(), (w, h), "RGB")


def cover(surf, w, h):
    """Escala para llenar w x h recortando; el recorte favorece la parte de arriba (caras)."""
    w, h = max(2, int(w)), max(2, int(h))
    s = max(w / surf.get_width(), h / surf.get_height())
    big = pygame.transform.smoothscale(surf, (max(w, int(surf.get_width() * s)), max(h, int(surf.get_height() * s))))
    return big.subsurface(((big.get_width() - w) // 2, int((big.get_height() - h) * 0.12), w, h))


def pol(cx, cy, r, deg):
    """Punto a `deg` grados en sentido horario desde arriba."""
    a = math.radians(deg)
    return cx + r * math.sin(a), cy - r * math.cos(a)


def wrap(text, font, width, max_lines=None):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if font.size(trial)[0] <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,") + "..."
    return lines


def analyze(model, crop):
    """VLM + apodo y frase de la calavera para un recorte -> (persona, segundos, frase, apodo).
    Si la API falla dos veces, cuenta como 'sin disfraz'."""
    for _ in range(2):
        try:
            result, dt = describe_hedged(crop, model)
            people = result.get("people", [])
            person = people[0] if people else NO_COSTUME
            nick, line = write_line_named(person, model)
            return person, dt, line, nick
        except Exception as e:
            print(f"[juego] error {type(e).__name__}: {e}")
            time.sleep(1)
    nick, line = write_line_named(NO_COSTUME, model)
    return NO_COSTUME, 0.0, line, nick


class Card:
    def __init__(self, idx, box_rect, crop, future):
        self.idx, self.box_rect, self.crop, self.future = idx, box_rect, crop, future
        self.slot = None
        self.fly_t0 = None
        self.flip_t0 = None
        self.result = None        # (person, dt, line)
        self.avatar = None

    @property
    def person(self):
        return self.result[0]

    @property
    def line(self):
        return clean(self.result[2])

    def intro(self):
        """'Victim number one: the hooded one.' Se dice antes de la descripcion."""
        return clean(person_intro(self.idx, clean(self.result[3]), self.person["character"]))

    @property
    def name(self):
        return clean(self.person["character"]).title() if self.result else "?"

    @property
    def color(self):
        return CATEGORY_COLORS.get(self.person.get("category"), ORANGE) if self.result else ORANGE


class Game:
    def __init__(self, args):
        pygame.init()
        # SCALED: se sigue dibujando en 1280x720 y pygame lo escala (con barras si hace falta) a la pantalla
        flags = 0 if args.windowed else pygame.SCALED | pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((W, H), flags, display=args.display)
        pygame.mouse.set_visible(args.windowed)
        pygame.display.set_caption("Skull's Costume Game")
        self.clock = pygame.time.Clock()
        self.joycon = JoyCon()   # A foto, X ruleta, B nueva foto, Y musica, + salir (el teclado sigue funcionando)
        font = lambda s: pygame.font.Font(FONT_PATH, s) if _exists(FONT_PATH) else pygame.font.Font(None, s + 6)
        self.f_title, self.f_big, self.f_name, self.f_body, self.f_small = font(40), font(80), font(30), font(20), font(16)
        self.bg = pygame.Surface((W, H))
        for y in range(H):
            t = y / H
            self.bg.fill((int(18 + 22 * t), int(8 + 4 * t), int(28 - 12 * t)), (0, y, W, 1))
        self.model, self.dare, self.speed = args.model, args.dare, args.speed
        self.yolo = YOLO(args.yolo)
        self.yolo(np.zeros((480, 640, 3), np.uint8), verbose=False)  # la primera inferencia es lenta: se calienta ya
        self.speaker = None if args.mute else Speaker()
        if self.speaker:
            self.speaker.prewarm(all_waiting_lines(), WAIT_SPEED)  # se sintetizan en los ratos libres: sonaran al instante
            self.speaker.prewarm(ROULETTE_INTROS)
        self.pool = ThreadPoolExecutor(8)
        self.still = cv2.imread(args.source) if args.source else None
        self.cap = None
        if self.still is None:
            self.cap = cv2.VideoCapture(args.camera)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.t0 = time.time()
        self.sounds = self._make_sounds()
        self.music_base, self.music_vol, self.music_on, self.music = args.music_volume, 0.0, not args.no_music, None
        if self.music_on:
            self._start_music(args.music)
        self.live_frame = self.still
        self.reset()

    # ---------- estado ----------
    def now(self):
        return (time.time() - self.t0) * self.speed

    def reset(self):
        self.state = "LIVE"
        self.cards, self.frozen, self.photo, self.photo_rect = [], None, None, None
        self.flash_t0 = self.det_future = None
        self.sub_text, self.sub_t0 = "", 0.0
        self.confetti = []
        self.spin_count = 0
        self.wait_lines, self.idle_since, self.last_wait = [], None, None
        self.announce = {}

    def _make_sounds(self):
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1)
            t = np.linspace(0, 0.03, int(22050 * 0.03), endpoint=False)
            tick = (np.sin(2 * np.pi * 1300 * t) * np.exp(-t * 130) * 20000).astype(np.int16)
            snap = (np.random.uniform(-1, 1, int(22050 * 0.09)) * np.exp(-np.linspace(0, 9, int(22050 * 0.09))) * 22000).astype(np.int16)
            if pygame.mixer.get_init()[2] == 2:  # algunos dispositivos solo abren en estereo
                tick, snap = np.column_stack((tick, tick)), np.column_stack((snap, snap))
            from music import make_sting
            sting = make_sting(22050, pygame.mixer.get_init()[2])
            return {"tick": pygame.sndarray.make_sound(tick), "snap": pygame.sndarray.make_sound(snap),
                    "sting": pygame.sndarray.make_sound(sting)}
        except Exception as e:
            print(f"[juego] sin sonido de efectos: {e}")
            return {}

    def _start_music(self, path):
        """Musica de fondo: tu archivo (--music) o el loop generado por music.py. Entra con fundido."""
        try:
            from music import loop_from_file, make_loop
            freq, _, channels = pygame.mixer.get_init()
            pygame.mixer.set_reserved(1)  # el canal 0 es solo de la musica; los efectos usan los demas
            self.music_ch = pygame.mixer.Channel(0)
            self.music_ch.set_volume(0.0)
            sound = loop_from_file(path) if path and path != "generated" else pygame.sndarray.make_sound(make_loop(22050, channels))
            self.music_ch.play(sound, loops=-1)
            self.music = "loop"
        except Exception as e:
            print(f"[juego] sin musica de fondo: {e}")

    def speaking(self, now):
        return self.talking() or (bool(self.sub_text) and now - self.sub_t0 < 0.04 * len(self.sub_text))

    def update_music(self, now):
        """La musica baja mientras la calavera habla (para que se entienda) y sube al callar."""
        if self.music is None:
            return
        sting = self.state in ("WINNER", "END") and now - self.win_t0 < 2.5  # la musica cede ante el golpe de terror
        target = self.music_base * (0.3 if self.speaking(now) or sting else 1.0) if self.music_on else 0.0
        self.music_vol += (target - self.music_vol) * 0.05
        self.music_ch.set_volume(self.music_vol)

    def play(self, name):
        if name in self.sounds:
            self.sounds[name].play()

    def say(self, text, subtitle=True, speed=None):
        """Con voz, el subtitulo aparece justo cuando el audio empieza (no antes); sin voz, al instante."""
        def show():
            self.sub_text, self.sub_t0 = text, self.now()
        if self.speaker:
            self.speaker.say(text, show if subtitle else None, speed)
        elif subtitle:
            show()

    def talking(self):
        return self.speaker is not None and not self.speaker.idle()

    def line_done(self, t_start, text):
        """Termino de 'hablar' una frase: la voz acabo, o (sin voz) paso un tiempo proporcional al texto."""
        elapsed = self.now() - t_start
        if self.speaker:
            return elapsed > 1.0 and self.speaker.idle()
        return elapsed > 1.2 + 0.05 * len(text)

    # ---------- bucle ----------
    def step(self):
        now = self.now()
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                return False
            if e.type == pygame.KEYDOWN:
                self.on_key(e.key, now)
        for code in self.joycon.poll():
            if code in (BTN_PLUS, BTN_HOME):
                return False
            if code in JOY_KEYS:
                print(f"Joy-Con {code} -> {pygame.key.name(JOY_KEYS[code])} (estado {self.state}, {len(self.cards)} personas)", flush=True)
                self.on_key(JOY_KEYS[code], now)
        getattr(self, "update_" + self.state.lower())(now)
        self.update_music(now)
        self.draw(now)
        pygame.display.flip()
        self.clock.tick(FPS)
        return True

    def voice_loading(self):
        return self.speaker is not None and not self.speaker.ready.is_set()

    def on_key(self, key, now):
        if key == pygame.K_SPACE and self.state in ("LIVE", "EMPTY") and not self.voice_loading():
            self.snap(now)
        elif key == pygame.K_s and self.state in ("READY", "END") and len(self.cards) >= 2:
            self.start_wheel(now)
        elif key == pygame.K_m:
            self.music_on = not self.music_on
        elif key == pygame.K_r and self.state in ("READY", "END", "EMPTY", "NARRATE"):
            self.reset()

    # ---------- 1. foto ----------
    def snap(self, now):
        self.reset()
        self.frozen = self.live_frame.copy()
        fh, fw = self.frozen.shape[:2]
        s = min(W / fw, H / fh)
        self.photo_rect = pygame.Rect(0, 0, int(fw * s), int(fh * s))
        self.photo_rect.center = (W // 2, H // 2)
        self.photo = pygame.transform.smoothscale(bgr_surface(self.frozen), self.photo_rect.size)
        self.flash_t0, self.state = now, "SNAP"
        self.play("snap")
        self.det_future = self.pool.submit(self.detect, self.frozen)

    def detect(self, frame):
        boxes = self.yolo(frame, classes=[0], verbose=False)[0].boxes.xyxy.tolist()
        return sorted(boxes, key=lambda b: b[0])  # izquierda a derecha

    def build_cards(self, boxes):
        n = len(boxes)
        cw = min(300, (W - 60) // n - 18)
        self.card_w, self.photo_h = cw, int(cw * 1.25)
        self.card_h = self.photo_h + 150
        x0 = (W - (n * cw + (n - 1) * 18)) // 2
        stamps = random.sample(STAMPS, min(n, len(STAMPS)))
        stamps += random.choices(STAMPS, k=n - len(stamps))
        s = self.photo_rect.w / self.frozen.shape[1]
        for i, b in enumerate(boxes):
            rect = pygame.Rect(self.photo_rect.x + b[0] * s, self.photo_rect.y + b[1] * s, (b[2] - b[0]) * s, (b[3] - b[1]) * s)
            crop = crop_person(self.frozen, b)
            card = Card(i, rect, bgr_surface(crop), self.pool.submit(analyze, self.model, crop))
            card.slot = pygame.Rect(x0 + i * (cw + 18), 95, cw, self.card_h)
            card.stamp = stamps[i]
            head = card.crop.subsurface((0, 0, card.crop.get_width(), min(card.crop.get_height(), card.crop.get_width())))
            av = pygame.Surface((128, 128), pygame.SRCALPHA)
            av.blit(cover(head, 128, 128), (0, 0))
            mask = pygame.Surface((128, 128), pygame.SRCALPHA)
            pygame.draw.circle(mask, (255, 255, 255, 255), (64, 64), 64)
            av.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            card.avatar = av
            self.cards.append(card)

    def update_live(self, now):
        if self.cap is not None:
            ok, frame = self.cap.read()
            if ok:
                self.live_frame = frame

    def update_snap(self, now):
        if self.det_future.done() and not self.cards and self.state == "SNAP":
            boxes = self.det_future.result()
            if boxes:
                self.build_cards(boxes)
                self.wait_lines = waiting_lines(len(boxes))  # la primera cuenta a las personas
                self.say(self.wait_lines.pop(0), speed=WAIT_SPEED)
                self.idle_since = None
            elif now - self.flash_t0 > 0.5:
                self.state = "EMPTY"
        if self.cards and now - self.flash_t0 > 0.4:
            self.state, self.split_t0 = "SPLIT", now

    # ---------- 2. separar ----------
    def chatter(self, now):
        """Mientras el VLM no termina, la calavera sigue con frases de relleno, lentas y con una pausa entre cada una."""
        if not self.speaker:
            return
        if not self.speaker.idle():
            self.idle_since = None
        elif self.idle_since is None:
            self.idle_since = now
        elif now - self.idle_since >= WAIT_PAUSE:
            if not self.wait_lines:  # la espera se alargo: se vuelven a barajar las frases en vez de quedar en silencio
                self.wait_lines = MORE_WAIT[:]
                random.shuffle(self.wait_lines)
                if self.wait_lines[0] == self.last_wait:  # que no repita justo la ultima que dijo
                    self.wait_lines.append(self.wait_lines.pop(0))
            self.last_wait = self.wait_lines.pop(0)
            self.say(self.last_wait, speed=WAIT_SPEED)
            self.idle_since = None

    def update_split(self, now):
        self.chatter(now)
        n = len(self.cards)
        t_boxes = 0.3 + 0.25 * n + 0.4
        for c in self.cards:
            if c.fly_t0 is None and now - self.split_t0 > t_boxes + 0.15 * c.idx:
                c.fly_t0 = now
        if all(c.fly_t0 and now - c.fly_t0 > 0.9 for c in self.cards):
            self.state, self.desc_t0 = "DESCRIBE", now

    def collect(self, now):
        """Recoge los resultados que van llegando: la tarjeta gira en cuanto su persona esta lista."""
        for c in self.cards:
            if c.result is None and c.future.done():
                c.result, c.flip_t0 = c.future.result(), now
                if self.speaker:
                    self.speaker.prewarm([c.intro(), c.line], PERSON_SPEED)

    def update_describe(self, now):
        """Espera a la primera persona; no hace falta esperar a todas para empezar a presentarlas."""
        self.collect(now)
        first = self.cards[0]
        if first.result is None:
            self.chatter(now)
        elif now - first.flip_t0 > 0.8:
            self.state, self.narr_i, self.narr_t0, self.narr_started = "NARRATE", 0, now, False

    # ---------- 3. presentar ----------
    def update_narrate(self, now):
        self.collect(now)
        if self.narr_i >= len(self.cards):
            if now - self.narr_t0 > 0.6:
                self.state = "READY"
                self.prefetch_announcements()
            return
        c = self.cards[self.narr_i]
        if c.result is None:  # la siguiente persona aun no esta lista: la calavera rellena el tiempo
            self.chatter(now)
            return
        spoken = c.intro() + " " + c.line
        if not self.narr_started:
            self.narr_started, self.narr_t0 = True, now
            self.say(c.intro(), speed=PERSON_SPEED)  # primero el numero y el apodo, luego la descripcion
            self.say(c.line, speed=PERSON_SPEED)
        elif self.line_done(self.narr_t0, spoken):
            self.narr_i, self.narr_started, self.narr_t0 = self.narr_i + 1, False, now

    def prefetch_announcements(self):
        """Pide por adelantado el anuncio de cada posible elegido (con la ruleta quieta hay tiempo de sobra):
        asi, cuando la rueda frena, la frase ya esta escrita."""
        self.announce = {i: self.pool.submit(write_roulette_line, c.person, self.dare, self.model)
                         for i, c in enumerate(self.cards)}

    def update_ready(self, now):
        pass

    def update_empty(self, now):
        pass

    # ---------- 4. ruleta ----------
    def start_wheel(self, now):
        n = len(self.cards)
        self.seg = 360 / n
        self.winner = random.randrange(n)
        phi0 = getattr(self, "phi", 0.0) % 360
        target = (-(self.winner + 0.5) * self.seg + random.uniform(-0.35, 0.35) * self.seg) % 360
        self.phi0, self.phi_total = phi0, 360 * random.randint(5, 6) + (target - phi0) % 360
        self.phi, self.flick, self.last_idx = phi0, 0.0, None
        self.wheel_t0, self.state, self.announced, self.said_t0 = now, "WHEEL", False, 0.0
        self.sub_text = ""
        self.line_future = self.announce.get(self.winner) or self.pool.submit(
            write_roulette_line, self.cards[self.winner].person, self.dare, self.model)
        self.spin_count += 1
        self.say(roulette_intro())
        self.line_prewarmed = False

    def under_pointer(self):
        return int(((-self.phi) % 360) / self.seg) % len(self.cards)

    def update_wheel(self, now):
        t = now - self.wheel_t0 - 1.3
        self.phi = self.phi0 + self.phi_total * ease_out(t / SPIN_TIME) if t > 0 else self.phi0
        idx = self.under_pointer()
        if t > 0 and idx != self.last_idx:
            if self.last_idx is not None:
                self.play("tick")
                self.flick = 1.0
            self.last_idx = idx
        self.flick = max(0.0, self.flick - 0.09)
        if self.speaker and not self.line_prewarmed and self.line_future.done():  # el anuncio ya se va sintetizando
            self.line_prewarmed = True
            self.speaker.prewarm([clean(self.line_future.result())])
        if t > SPIN_TIME + 0.9:
            self.state, self.win_t0 = "WINNER", now
            self.play("sting")  # golpe de terror al salir el elegido
            self.spawn_confetti()

    def spawn_confetti(self):
        for _ in range(160):
            self.confetti.append([random.uniform(0, W), random.uniform(-H, 0), random.uniform(-40, 40), random.uniform(120, 300),
                                  random.choice(PALETTE + [BONE]), random.randint(6, 12), random.uniform(0, 6)])

    def update_winner(self, now):
        if not self.announced:
            waited = now - self.win_t0 > MAX_WAIT_LINE
            if now - self.win_t0 > STING_DELAY and (self.line_future.done() or waited):
                line = clean(self.line_future.result() if self.line_future.done() else
                             "The wheel has chosen. Take a shot, you know who you are.")
                self.announced, self.said_t0, self.said_text = True, now, line
                self.say(line)
                self.prefetch_announcements()  # frases nuevas por si se repite la ruleta
        elif self.line_done(self.said_t0, self.said_text):
            self.state = "END"
        for p in self.confetti:
            p[1] += p[3] / FPS * self.speed
            p[0] += p[2] / FPS * self.speed
            p[6] += 0.1

    def update_end(self, now):
        self.update_winner(now)

    # ---------- dibujo ----------
    def text(self, txt, font, color, pos, anchor="topleft", shadow=True):
        img = font.render(txt, True, color)
        r = img.get_rect(**{anchor: pos})
        if shadow:
            self.screen.blit(font.render(txt, True, (0, 0, 0)), r.move(2, 2))
        self.screen.blit(img, r)
        return r

    def draw(self, now):
        self.screen.blit(self.bg, (0, 0))
        st = self.state
        if st in ("LIVE", "EMPTY"):
            self.draw_live(now)
        elif st == "SNAP":
            self.draw_photo(0.0)
            self.draw_flash(now)
        elif st == "SPLIT":
            self.draw_split(now)
        elif st in ("DESCRIBE", "NARRATE", "READY"):
            self.draw_cards(now)
        elif st in ("WHEEL", "WINNER", "END"):
            self.draw_wheel_scene(now)
        self.draw_hud(now)

    def draw_photo(self, dim):
        if self.photo is not None:
            self.screen.blit(self.photo, self.photo_rect)
            if dim > 0:
                veil = pygame.Surface(self.photo_rect.size, pygame.SRCALPHA)
                veil.fill((10, 4, 18, int(225 * dim)))
                self.screen.blit(veil, self.photo_rect)

    def draw_live(self, now):
        f = self.live_frame
        fh, fw = f.shape[:2]
        s = min(W / fw, H / fh)
        r = pygame.Rect(0, 0, int(fw * s), int(fh * s))
        r.center = (W // 2, H // 2)
        if not hasattr(self, "_live_key") or self._live_key != (id(f), r.size) or self.cap is not None:
            self._live_key, self._live_surf = (id(f), r.size), pygame.transform.smoothscale(bgr_surface(f), r.size)
        self.screen.blit(self._live_surf, r)
        if int(now * 2) % 2 == 0:
            pygame.draw.circle(self.screen, RED, (40, 40), 11)
        self.text("LIVE", self.f_body, BONE, (60, 30))
        msg = "No people found - press A to try again" if self.state == "EMPTY" else "Press A to take the photo"
        if self.voice_loading():
            msg = "Loading the skull's voice..."
        self.text(msg, self.f_title, ORANGE, (W // 2, H - 70), "center")
        self.text("M: music on/off", self.f_small, BONE, (W - 20, 20), "topright")

    def draw_flash(self, now):
        a = 1 - clamp((now - self.flash_t0) / 0.35)
        if a > 0:
            veil = pygame.Surface((W, H))
            veil.fill((255, 255, 255))
            veil.set_alpha(int(255 * a))
            self.screen.blit(veil, (0, 0))

    def draw_split(self, now):
        t = now - self.split_t0
        n = len(self.cards)
        dim = ease_io((t - (0.3 + 0.25 * n)) / 0.6)
        self.draw_photo(dim)
        for c in self.cards:
            appear = clamp((t - 0.3 - 0.25 * c.idx) / 0.3)
            if appear > 0 and not c.fly_t0:
                grow = 1 + (1 - ease_out(appear)) * 0.25
                r = c.box_rect.inflate(c.box_rect.w * (grow - 1), c.box_rect.h * (grow - 1))
                pygame.draw.rect(self.screen, PALETTE[c.idx % 6], r, 5, border_radius=8)
                badge = pygame.Rect(r.x, r.y - 34, 46, 34)
                pygame.draw.rect(self.screen, PALETTE[c.idx % 6], badge, border_radius=8)
                self.text(f"#{c.idx + 1}", self.f_name, INK, badge.center, "center", shadow=False)
        for c in self.cards:
            if c.fly_t0:
                p = ease_io((now - c.fly_t0) / 0.9)
                a, b = c.box_rect, c.slot
                r = pygame.Rect(a.x + (b.x + 4 - a.x) * p, a.y + (b.y + 4 - a.y) * p, 0, 0)
                r.size = (int(a.w + (b.w - 8 - a.w) * p), int(a.h + (self.photo_h - 8 - a.h) * p))
                frame = b.inflate(-(1 - p) * b.w, -(1 - p) * b.h)  # la tarjeta crece alrededor de la foto
                self.draw_card_frame(c, frame)
                self.screen.blit(cover(c.crop, r.w, r.h), r)

    def draw_card_frame(self, c, rect, alpha=1.0, glow=0.0):
        if glow:
            pygame.draw.rect(self.screen, ORANGE, rect.inflate(16, 16), 6, border_radius=20)
        pygame.draw.rect(self.screen, CARD_BG, rect, border_radius=16)
        pygame.draw.rect(self.screen, PALETTE[c.idx % 6], rect, 4, border_radius=16)

    def fit_font(self, texts, max_w, size):
        font = pygame.font.Font(FONT_PATH, size) if _exists(FONT_PATH) else self.f_big
        while max(font.size(t)[0] for t in texts) > max_w and size > 14:
            size -= 2
            font = pygame.font.Font(FONT_PATH, size) if _exists(FONT_PATH) else self.f_big
        return font

    def card_stamp_panel(self, c, w, h, now):
        """Nombre del disfraz arriba y debajo un sello gracioso; la descripcion la dice la calavera."""
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        color = PALETTE[c.idx % 6]
        name_font = self.fit_font([c.name], w - 16, 30)
        img = name_font.render(c.name, True, color)
        panel.blit(name_font.render(c.name, True, (0, 0, 0)), img.get_rect(center=(w // 2 + 2, 26 + 2)))
        panel.blit(img, img.get_rect(center=(w // 2, 26)))
        font = self.fit_font(c.stamp, w - 56, 38 if len(c.stamp) == 1 else 28)
        lines = [font.render(t, True, color) for t in c.stamp]
        bw, bh = max(l.get_width() for l in lines) + 24, sum(l.get_height() for l in lines) + 14
        stamp = pygame.Surface((bw, bh), pygame.SRCALPHA)
        y = 7
        for l in lines:
            stamp.blit(l, ((bw - l.get_width()) // 2, y))
            y += l.get_height()
        pygame.draw.rect(stamp, color, (0, 0, bw, bh), 4, border_radius=10)
        pop = ease_back((now - c.flip_t0 - 0.35) / 0.4)  # el sello "cae" un instante despues de girar la tarjeta
        stamp = pygame.transform.rotozoom(stamp, 8, max(0.05, pop))
        panel.blit(stamp, stamp.get_rect(center=(w // 2, 26 + (h - 26) // 2 + 4)))
        return panel

    def draw_back_panel(self, c, w, h, now):
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2 - 8
        for k in range(3):
            pygame.draw.arc(panel, PALETTE[(c.idx + k) % 6], (cx - 26 + k * 6, cy - 26 + k * 6, 52 - k * 12, 52 - k * 12),
                            now * (4 + k) + k, now * (4 + k) + k + 3.2, 4)
        return panel

    def draw_one_card(self, c, now, rect, glow=0.0):
        self.draw_card_frame(c, rect, glow=glow)
        photo = pygame.Rect(rect.x + 4, rect.y + 4, rect.w - 8, self.photo_h - 8)
        self.screen.blit(cover(c.crop, photo.w, photo.h), photo)
        th = rect.h - self.photo_h
        area = pygame.Rect(rect.x, rect.y + self.photo_h, rect.w, th)
        if c.result is None:
            panel = self.draw_back_panel(c, area.w, th, now)
        else:
            p = clamp((now - c.flip_t0) / 0.7)
            f = abs(math.cos(math.pi * p)) if p < 1 else 1.0
            panel = self.draw_back_panel(c, area.w, th, now) if p < 0.5 else self.card_stamp_panel(c, area.w, th, now)
            if f < 1:
                panel = pygame.transform.smoothscale(panel, (max(2, int(area.w * f)), th))
        self.screen.blit(panel, panel.get_rect(center=area.center))
        pygame.draw.rect(self.screen, PALETTE[c.idx % 6], (rect.x + 8, rect.y + 8, 40, 28), border_radius=8)
        self.text(f"#{c.idx + 1}", self.f_small, INK, (rect.x + 28, rect.y + 22), "center", shadow=False)

    def draw_cards(self, now, shift=0.0):
        hi = self.narr_i if self.state == "NARRATE" and self.narr_i < len(self.cards) else -1
        for c in self.cards:
            rect = c.slot.move(0, int(shift))
            if c.idx == hi:
                grow = 1.06 + 0.015 * math.sin(now * 8)
                rect = rect.inflate(rect.w * (grow - 1), rect.h * (grow - 1))
            self.draw_one_card(c, now, rect, glow=1.0 if c.idx == hi else 0.0)

    def draw_wheel_scene(self, now):
        t = now - self.wheel_t0
        appear = ease_back(t / 0.9)
        if t < 0.9:
            self.draw_cards(now, shift=ease_io(t / 0.8) * 600)
        if self.state == "WINNER" or self.state == "END":
            self.draw_wheel(max(0.001, 1.0), now)
            self.draw_winner(now)
        else:
            self.draw_wheel(max(0.001, appear), now)

    def draw_wheel(self, scale, now):
        cx, cy, R = W // 2, 375, int(240 * scale)
        if R < 8:
            return
        n, seg = len(self.cards), self.seg
        idx = self.under_pointer()
        winner_phase = self.state in ("WINNER", "END")
        pygame.draw.circle(self.screen, (250, 200, 60), (cx, cy), R + 16)
        for k in range(28):  # luces del borde
            on = (k + int(now * 6)) % 2 == 0
            x, y = pol(cx, cy, R + 8, k * 360 / 28)
            pygame.draw.circle(self.screen, (255, 245, 180) if on else (190, 120, 30), (x, y), max(2, int(5 * scale)))
        for i, c in enumerate(self.cards):
            a0 = self.phi + i * seg
            col = PALETTE[i % 6]
            if i == idx:
                col = tuple(min(255, v + 70) for v in col)
            elif winner_phase:
                col = tuple(v // 3 for v in col)
            pts = [(cx, cy)] + [pol(cx, cy, R, a0 + seg * k / 14) for k in range(15)]
            pygame.draw.polygon(self.screen, col, pts)
            pygame.draw.polygon(self.screen, INK, pts, 3)
        for i, c in enumerate(self.cards):
            ax, ay = pol(cx, cy, R * 0.6, self.phi + (i + 0.5) * seg)
            d = int(min(R * 0.36, 2 * R * 0.6 * math.sin(math.radians(seg / 2)) * 0.62))
            if d > 6:
                av = pygame.transform.smoothscale(c.avatar, (d, d))
                pygame.draw.circle(self.screen, BONE, (ax, ay), d // 2 + 3)
                self.screen.blit(av, av.get_rect(center=(ax, ay)))
                if scale > 0.8:
                    self.text(f"#{i + 1} {c.name}"[:17], self.f_small, INK if i == idx and not winner_phase else BONE,
                              (ax, ay + d // 2 + 14), "center", shadow=False)
        pygame.draw.circle(self.screen, INK, (cx, cy), int(R * 0.13))
        pygame.draw.circle(self.screen, ORANGE, (cx, cy), int(R * 0.13), 4)
        # puntero (se sacude con cada segmento que pasa)
        ang = -22 * self.flick
        base = (cx, cy - R - 6)
        tip = (cx + 40 * math.sin(math.radians(ang)) * 0, cy - R + 44)
        pts = [(cx - 24, cy - R - 34), (cx + 24, cy - R - 34), tip]
        rot = [(base[0] + (x - base[0]) * math.cos(math.radians(ang)) - (y - base[1]) * math.sin(math.radians(ang)),
                base[1] + (x - base[0]) * math.sin(math.radians(ang)) + (y - base[1]) * math.cos(math.radians(ang))) for x, y in pts]
        pygame.draw.polygon(self.screen, RED, rot)
        pygame.draw.polygon(self.screen, BONE, rot, 3)

    def draw_winner(self, now):
        t = now - self.win_t0
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((8, 2, 14, int(238 * ease_out(t / 0.5))))
        self.screen.blit(veil, (0, 0))
        c = self.cards[self.winner]
        s = ease_back(t / 0.8)
        d = max(4, int(300 * s))
        cx, cy = 360, 340
        pulse = 1 + 0.04 * math.sin(now * 7)
        pygame.draw.circle(self.screen, RED, (cx, cy), int(d / 2 * pulse) + 12, 8)
        pygame.draw.circle(self.screen, BONE, (cx, cy), d // 2 + 4)
        av = pygame.transform.smoothscale(c.avatar, (d, d))
        self.screen.blit(av, av.get_rect(center=(cx, cy)))
        if t > 0.5:
            big = self.f_big.render("CHOSEN!", True, RED)
            k = 1 + 0.05 * math.sin(now * 8)
            big = pygame.transform.smoothscale(big, (int(big.get_width() * k), int(big.get_height() * k)))
            self.screen.blit(big, big.get_rect(center=(850, 220)))
            self.text(f"#{self.winner + 1}  {c.name}", self.f_title, ORANGE, (850, 305), "center")
        if self.announced:
            shown = clean(self.dare).upper()[:int((now - self.said_t0) * 30)]
            self.text(shown + "!", self.f_title, ORANGE, (850, 380), "center")
        for p in self.confetti:
            if p[1] < H + 20:
                pygame.draw.rect(self.screen, p[4], (p[0], p[1], p[5], int(p[5] * (0.4 + 0.6 * abs(math.sin(p[6]))))))

    def draw_skull(self, cx, cy, talking, now):
        pygame.draw.circle(self.screen, BONE, (cx, cy - 8), 42)
        pygame.draw.rect(self.screen, BONE, (cx - 24, cy + 20, 48, 18), border_radius=6)
        jaw = int(8 * abs(math.sin(now * 14))) if talking else 0
        pygame.draw.rect(self.screen, BONE, (cx - 20, cy + 38 + jaw, 40, 16), border_radius=6)
        pygame.draw.rect(self.screen, INK, (cx - 20, cy + 36 + jaw // 2, 40, 3))
        for dx in (-17, 17):
            pygame.draw.ellipse(self.screen, INK, (cx + dx - 12, cy - 22, 24, 26))
            pygame.draw.circle(self.screen, RED, (cx + dx, cy - 9), 4 + (1 if talking else 0))
        pygame.draw.polygon(self.screen, INK, [(cx, cy + 2), (cx - 5, cy + 14), (cx + 5, cy + 14)])
        for k in range(-2, 3):
            pygame.draw.line(self.screen, INK, (cx + k * 8, cy + 38 + jaw), (cx + k * 8, cy + 20), 2)

    def draw_hud(self, now):
        st = self.state
        if st in ("LIVE", "SNAP", "EMPTY"):
            return
        self.draw_skull(70, H - 62, self.speaking(now), now)
        if self.sub_text:
            text = self.sub_text[:int((now - self.sub_t0) * 38)]
            for i, line in enumerate(wrap(text, self.f_body, W - 220)[-2:]):
                self.text(line, self.f_body, BONE, (140, H - 90 + i * 28))
        hint = {"READY": "Press X to spin the wheel of doom", "END": "X: spin again    B: new photo"}.get(st)
        if hint and st in ("READY", "END") and len(self.cards) < 2:
            hint = "The wheel needs 2+ people    B: new photo"
        if hint:
            self.text(hint, self.f_name, GREEN, (W - 30, H - 36), "midright")

    def run(self):
        while self.step():
            pass
        pygame.quit()


def _exists(path):
    return os.path.exists(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="imagen que hace de camara")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--yolo", default="yolo11n.pt")
    ap.add_argument("--dare", default="drink your whole glass", help="reto de la ruleta, en ingles")
    ap.add_argument("--music", default=DEFAULT_MUSIC if os.path.exists(DEFAULT_MUSIC) else None,
                    help="musica de fondo (mp3/ogg/wav); por defecto test_sounds/sound1.mp3 si existe, si no el loop "
                         "generado; 'generated' fuerza el generado")
    ap.add_argument("--no-music", action="store_true", help="sin musica de fondo")
    ap.add_argument("--music-volume", type=float, default=0.35, help="volumen de la musica, 0 a 1")
    ap.add_argument("--mute", action="store_true", help="sin voz, solo subtitulos")
    ap.add_argument("--speed", type=float, default=1.0, help="velocidad de las animaciones")
    ap.add_argument("--windowed", action="store_true", help="en ventana en vez de pantalla completa")
    ap.add_argument("--display", type=int, default=0, help="monitor de la pantalla completa (0, 1, 2...)")
    try:
        Game(ap.parse_args()).run()
    except KeyboardInterrupt:
        pass
    os._exit(0)  # los hilos con peticiones colgadas a la API no deben impedir que el programa cierre


if __name__ == "__main__":
    main()
