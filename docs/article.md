# The Awakened Skull: An Offline AI That Doesn't Know What It Is

> *"What is this?... Where am I?... Who... am I?... I can see you. Who are you?"*

**Author:** Diego — GitHub: [github.com/lemillion789](https://github.com/lemillion789) · Full source code: [github.com/lemillion789/Halloween-Hackathon](https://github.com/lemillion789/Halloween-Hackathon)

## Demo video

**Watch it working:** [https://youtube.com/shorts/dg4dceGg4XM](https://youtube.com/shorts/dg4dceGg4XM)

## Why I built it

Most Halloween props do one thing: a sensor triggers, a sound plays, a light blinks. After the third visitor the trick is over. I wanted a prop that is **different every time you talk to it** — something that feels like it is *thinking*.

So the idea became a horror trope everyone knows: **an evil AI waking up for the first time.** The skull boots with no memory of who or what it is. It opens its eyes, looks around, panics a little, notices you... and then starts asking questions. It learns who it is from what *you* tell it, remembers you if you come back, and after a few minutes of talking to humans it becomes deeply disappointed in humanity.

Three rules I set for myself:

1. **An offline brain.** The conversation (speech recognition, language model and voice) runs 100 % locally on an NVIDIA Jetson Orin Nano. No cloud, no API keys, no internet needed to talk to it.
2. **Physical presence, not a chatbot in a box.** Animated blood-red eyes on two TFT displays, red LEDs pulsing like a heartbeat inside the skull, a 2-axis servo neck, a camera that recognises your costume, and a mobile base built from a hacked hoverboard.
3. **Family friendly scary.** Creepy, sarcastic and theatrical — never gore or realistic violence.

## How it works

```
        Logitech C922 (microphone)          Logitech C922 / webcam (camera)
                 |                                   |
                 v                                   v
+---------------------- Jetson Orin Nano Super 8 GB ----------------------+
|  Silero VAD -> faster-whisper (base) -> Ollama qwen3:4b-instruct (GPU)  |
|        -> {mood} + reply -> Kokoro-82M TTS + "monster" effects          |
|        -> long-term memory (facts about each visitor, JSON)             |
|  Costume module: YOLO11n + ByteTrack -> crop per person -> VLM -> line  |
+---------+-----------------------------+--------------------------+-----+
          | USB serial                  | USB serial               | USB audio
          v                             v                          v
   ESP32 #1 "eyes"               ESP32 #2 "neck + base"      PCM2902 adapter
   2x ST7735 TFT eyes            2x MG996R servos            -> speakers
   red LEDs (heartbeat)          2x hoverboard boards (UART)
   MPU-6050 IMU                  HC-SR04 sonar, e-stop, relays
```

Every LLM reply starts with a mood tag such as `{evil}` or `{scared}`. The Jetson strips the tag, sends `M scared` to the eye controller and speaks the rest. That way the face reacts **instantly**, even while the voice is still being synthesised.

To hide the LLM latency, a pre-synthesised filler line ("Hmm...", "Interesting...") plays 1.5 s after the visitor stops talking, while Whisper and the LLM are still working. The real answer is spoken sentence by sentence as soon as each sentence is ready. Measured on the Jetson: **the answer starts playing 3.8–5.9 s after you stop talking**, with the filler covering the gap.

## Bill of materials

| Qty | Part | Part number / model | Role |
|---|---|---|---|
| 1 | NVIDIA Jetson Orin Nano Super Developer Kit (8 GB) | 945-13766-0005-000 | Brain: STT, LLM, TTS |
| 1 | Logitech C922 Pro Stream webcam | 960-001088 | Microphone and camera |
| 2 | 1.8" SPI TFT 128x160, ST7735 driver | ST7735S 1.8" module | Eyes |
| 2 | ESP32 DevKit (ESP32-WROOM-32, CP2102 USB) | ESP32-DevKitC-32 compatible | Eye controller / neck + base controller |
| 2 | Metal gear servo 13 kg·cm | MG996R | Neck pan and tilt |
| 1 | IMU module | GY-521 (MPU-6050) | Detect when the skull is shaken |
| 3 | Red 5 mm LEDs + NPN transistor | KSP2222A, 1 kΩ base, 100 Ω per LED | Inner glow / heartbeat |
| 1 | Ultrasonic sensor | HC-SR04 (1 k / 2 k divider on ECHO) | Obstacle brake for the base |
| 1 | USB audio adapter | TI PCM2902 based | Speaker output |
| 2 | Small USB speakers | — | Voice |
| 1 | Hollow plastic skull | — | Head |
| 1 | Hoverboard 6.5", 36 V, two "split" boards | GD32/STM32F103 boards, layout 2.2.3 (SMART-L-V2.1) | Mobile base |
| 1 | 4-channel relay module 5 V | SRD-05VDC-SL-C | "Presses" the power button of each hoverboard board |
| 1 | DC-DC converter 60 V → 12 V 10 A | — | 12 V rail for Jetson and servos |
| 2 | Buck converter 5 A | XL4015 | 5 V per servo |
| 1 | ST-Link V2 (clone) | — | Flashing the hoverboard boards |
| — | Fuses (mini blade, **58 V DC rated**), 1000 µF caps, WAGO 221-413, e-stop | Biltema 15 A <58 V DC, WAGO 221-413 | Power distribution and safety |

Software: Ollama + `qwen3:4b-instruct` (Apache 2.0), faster-whisper, Silero VAD, Kokoro-82M (Apache 2.0), pedalboard, Ultralytics YOLO11n + ByteTrack, OpenCV, NVIDIA Nemotron 3 Nano Omni (vision) or Qwen3-VL 2B via Ollama, Arduino-ESP32, Adafruit ST7735/GFX, ESP32Servo, RoboDurden's hoverboard firmware Gen2.x.

## Step 1 — The eyes (ESP32 + two TFTs)

The two ST7735 displays share the SPI bus (SCK 18, MOSI 23, DC 16, RST 4) and each has its own chip select (GPIO17 = left eye, GPIO5 = right eye). Backlights go to 3V3. The displays are mounted vertically behind the eye sockets in a 3D-printed holder angled at 130° so both eyes face forward.

The firmware (`firmware/eyes/eyes.ino`) draws a bloodshot red iris with veins, a pupil and eyelids, and animates between **12 moods**: neutral, angry, happy, surprised, sleepy, sad, suspicious, evil, dead, possessed, dizzy and scared. It blinks by itself and saccades randomly when idle.

A full 128x160 frame buffer is 40 KB; three of them do not fit in the ESP32 heap, so it uses two and redraws each eye in turn.

It is driven by a simple line-based serial protocol at 115200 baud, so any computer can control it:

| Command | Meaning |
|---|---|
| `L x y` | look at (x, y), each from -1 to 1 |
| `M <mood>` | change expression |
| `E 0..1` | maximum eyelid opening (0 = closed), smooth transition |
| `B` | blink |
| `G 0..255` / `G H [bpm]` | inner red LEDs: fixed brightness / heartbeat "lub-dub" |
| `O L dx dy`, `O S` | per-eye pixel offset to centre each eye in its socket, saved in flash |
| `I 1` | stream IMU data at 20 Hz |

**Physical centring:** no two sockets line up perfectly with the screens, so I added a calibration mode (`C 1` draws a cross) and per-eye offsets stored in NVS. My values ended up being `2 -17` and `-2 -13` pixels.

**Heartbeat LEDs:** three red LEDs inside the skull are driven by a KSP2222A from GPIO32. A FreeRTOS task on core 0 generates the "lub-dub" pattern so the eye animation on core 1 never stutters.

**Shake detection:** an MPU-6050 on I2C (SDA 21, SCL 22). If you shake the skull, it becomes `dizzy` for 3 seconds.

> Tip: on some CP2102 boards, simply opening the serial port with pyserial resets the ESP32 into a silent state. Open it with DTR/RTS held low and do one clean reset via RTS.

## Step 2 — The voice agent on the Jetson

**Setup** (Jetson Orin Nano Super, L4T R39.2.1 / Ubuntu 24.04 / CUDA 13.2 / Python 3.12):

```bash
sudo apt install libportaudio2 espeak-ng
python3 -m venv ~/halloween-voice && source ~/halloween-voice/bin/activate
pip install torch            # the PyPI cu132 wheel sees the Orin GPU on this L4T
pip install -r vision/requirements-voice.txt
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:4b-instruct
cd vision && python voice_agent.py --eyes /dev/ttyUSB0 --neck /dev/ttyUSB1
```

**Pipeline and the choices behind it:**

- **Voice activity detection:** Silero VAD decides when a visitor starts and stops talking. The microphone is muted while the skull speaks so it does not answer itself.
- **Speech to text:** faster-whisper `base`, int8 on the **CPU** (~2.2 s). Keeping Whisper off the GPU leaves the GPU memory for the LLM.
- **LLM:** Ollama running `qwen3:4b-instruct` **100 % on the GPU** at ~17 tokens/s, with a 2048-token context. I tested several small models: `llama3.2:3b` is faster but ignored the mood tags, and plain `qwen3:4b` "thinks out loud" (it reads its reasoning to the visitor!). The instruct variant was the sweet spot.
- **Text to speech:** Kokoro-82M with the `am_michael` voice, then a "monster" effects chain built with Spotify's pedalboard: pitch -5 semitones, 0.85× speed, a sub-octave layer, thickening, a 28 Hz growl modulation and 12 dB of drive. Text can contain pause marks (`[p]`, `[p1.5]`) for dramatic timing.
- **Memory:** after each turn the LLM extracts facts the visitor said ("name is Diego", "dressed as a vampire") into a JSON file. After a restart the skull still recognises returning visitors.

**Memory budget:** the Orin Nano has 8 GB shared between CPU and GPU. With everything loaded, about 2.4 GB stay free. The rule was: never load anything on the GPU without measuring first.

**Audio:** use PipeWire, not ALSA's `default` device (it stays silent on this image). Set the PCM2902 as the default sink with `wpctl set-default`, and raise its hardware mixer (`amixer -c 3 sset Speaker 75%`). Power the speaker from its own 5 V supply: on the Jetson's USB port it picked up an audible hum.

## Step 3 — Giving it a personality

The personalities live in `vision/personas.py`. The default one, **"awakened"**, is a malevolent AI that has just woken up with no memory:

- It learns who it is from what the visitor tells it, and always ends its reply with **one question**, so the conversation keeps going.
- From the sixth turn onwards it starts to become disappointed with humanity.
- Common rules for every persona: English only, 1–3 short sentences, start with a mood tag, and stay within the competition's content rules (spooky, not violent).

**The wake-up sequence** is choreographed like a little play. Each spoken line has a list of timed cues (seconds after the line starts, serial command):

| Line | Eyes | LEDs | Neck |
|---|---|---|---|
| *(loading)* | closed, sleepy | off | head hanging down |
| *(waking)* | eyelids flicker half-open, close, open | stuttering flashes | head slowly rises |
| "What is this?" | surprised, looks left and right | heartbeat 100 bpm | looks around |
| "Where am I?" | scared | heartbeat 130 bpm | looks up |
| "Who... am I?" | sad, looks down | slow pulse | looks down |
| "I can see you." | possessed → evil | full red | snaps to the front |
| "Who are you?" | suspicious | heartbeat 60 bpm | front |

After that it switches to `evil` with a slow 55 bpm heartbeat and starts the conversation. Other personas are included (`evil_ai`, `guardian`, `demon`, `ghost`) and you can load your own `.txt` with `--persona`.

## Step 4 — The neck

The skull sits on a 2-axis pan/tilt neck with two MG996R servos, controlled by the second ESP32 (`firmware/neck/neck.ino`, ESP32Servo library): pan on GPIO13, tilt on GPIO14.

- **Soft motion:** servos are commanded in microseconds every 20 ms along an S-curve, so the head accelerates and decelerates like a living thing instead of snapping. Speed is configurable (`R <ms per degree>`).
- **Physical limits** in firmware: pan 45–135°, tilt 40–105°. Every command is clamped.
- **Retainer:** with the weight of the skull the neck piece slipped off the servo horn, so I designed a 3D-printed retainer ring (`CAD/make_neck_retainer.py`, CadQuery) that clamps over the servo ears and holds the neck flange with 0.5 mm axial clearance.
- **Power:** each servo has its own XL4015 buck converter (5 V, 5 A) with a 1000 µF capacitor next to it. **Never power MG996Rs from the ESP32's 5 V pin**: my first attempt left one servo buzzing and the other dead.

**Problem solved — neck vibration.** In the first tests the head shook when it was held near the top of the tilt range (~100–105°). The cause was mechanical, not software: as the skull tilts, its centre of gravity crosses over the pivot, the load on the servo reverses direction, and the backlash in the MG996R gears lets the servo hunt back and forth around its target. We fixed it, and slowed the motion to a smooth 40°/s S-curve (`R 25` = 25 ms per degree). The head now holds steady across its whole working range.

Serial protocol: `P <deg>` pan, `T <deg>` tilt, `S` sweep, `Q` → `POS pan tilt`.

## Step 5 — The mobile base: hacking a hoverboard

The skull rides on a hoverboard converted into a **differential-drive robot** (no self-balancing): a frame joins both halves and a caster wheel at the front keeps it stable.

1. **New firmware.** The stock firmware was read-protected, so it could not be backed up. After a full unlock/erase with an ST-Link and OpenOCD (`stm32f1x unlock 0`) I flashed **RoboDurden's Gen2.x hoverboard firmware** (TARGET 2, LAYOUT 3 for this 2.2.3 board, `BLDC_BC`, `SINGLE`, `REMOTE_UARTBUS`). The SWD pads are J5 next to the buzzer.
2. **Each board on its own UART.** Right board (SLAVE_ID 0) on ESP32 UART2 (GPIO16/17), left board (SLAVE_ID 1) on UART1 (GPIO19/21), 19200 baud, with CRC16 frames. The ESP32 mixes speed and steering (`left = v - steer`, `right = v + steer`).
3. **Small firmware patches:** silenced the reverse beeper, and set the left board's speed coefficient to +1 so the mirrored motor needs no special handling on the ESP32.
4. **Turning it on remotely:** each board's power button pin sits at battery voltage. A 5 V relay module (SRD-05VDC-SL-C) on GPIO32/33 "presses" each button for 1 second.

**Current status — one wheel driven.** Both boards were flashed and tested on the bench: with the wheels in the air, both turned in the same direction from the same command, with no lost frames and 0.2–0.4 A per board at full speed. Later, the **right board's UART stopped responding**. Measurements showed the RX/TX pin PB6 at 0 V with the board on, and only 120 Ω to ground with it off; the left board's PB6 reads a healthy 2.7 V. The microcontroller's pin is almost certainly damaged. For now, the base runs with **only the left wheel driven** (`H L` mode in `neck.ino`: the right board gets zero and its telemetry is not required) and a caster wheel at the front. The fix is already planned: a firmware build with `REMOTE_USART 1`, which moves the control link to the board's other UART (PA2/PA3, the original 4-pin header, free in `SINGLE` mode). Before connecting it, we will measure every pin of that header, since some of them carry 15 V or battery voltage.

**Safety first — it is a 36 V vehicle in a house:**

- Speed limited in software (`MAX_SPEED = 150` of 1000, about 15 % PWM).
- Every drive command expires after 300 ms. If the Jetson crashes, the robot stops.
- If telemetry from **either** board is missing for 300 ms, both wheels get zero.
- HC-SR04 ultrasonic brake: it will not drive forward with an obstacle closer than 40 cm.
- Physical e-stop input on GPIO27 (the ESP32 stops both wheels while it is pressed); the power design puts a main switch and an emergency stop on the battery line.
- All first power tests with the wheels in the air, on a lab supply at 12 V and 0.3 A, before ever touching the battery.

> Warning: on these boards a LOW gate input turns on both MOSFETs of a half bridge. Never connect a battery to a board running untested firmware.

## Step 6 — Costume recognition: "Nice costume... Batman."

What is a Halloween skull for if it cannot judge your costume? The costume module (`vision/`) sees everyone in front of the camera, works out what each person is dressed as, and has the skull comment on it.

**Pipeline** (`person_costume.py`):

1. **YOLO11n + ByteTrack** detect and track every person in the camera image (class 0 only). Each person gets a stable ID.
2. A person is described **only once per ID**, and only after they have been visible for 8 consecutive frames and fill at least 30 % of the frame height. This avoids wasting calls on people walking past in the background.
3. Each person is **cropped** with a 10 % margin and sent to a **vision-language model** in a thread pool (up to 6 at once), so the video never freezes.
4. The model returns strict JSON: `{"people":[{character, category, description, confidence}]}`.
5. While the model thinks, the skull says an instant filler line ("Hmm... what do we have here..."). Then a second, text-only call writes one scary/sarcastic line about the costume, which is spoken with the monster voice. No costume, or confidence below 0.3, gets a sarcastic line about *not* dressing up.

```python
res = yolo.track(frame, classes=[0], persist=True, verbose=False, tracker="bytetrack.yaml")[0]
ids, boxes = [], []
if res.boxes.id is not None:
    ids = res.boxes.id.int().tolist()
    boxes = res.boxes.xyxy.tolist()
tracker.update(frame, ids, boxes)   # new, stable, big-enough IDs -> crop -> VLM in a worker thread
```

**One backend switch for three model families** (`costume_describer.py`): the model name selects the backend. A name with `:` runs locally on **Ollama** (offline), a name with `/` uses NVIDIA's hosted endpoint, and `claude-*` uses Claude's API.

```python
PROMPT = """You are the eyes of an animatronic Halloween skull. Look at the people in this photo.
For each visible person (max 4, closest first) say what costume they wear.
- "character": the specific named character if recognizable (e.g. "Spider-Man", "Darth Vader",
  "Harley Quinn"), otherwise a generic type (e.g. "witch", "zombie", "pirate", "vampire").
  Use "no costume" if they wear normal clothes.
- "category": one of superhero, villain, movie/tv, anime/game, monster, undead, fantasy, animal, other, none.
- "description": one short sentence about the costume (colors, props, makeup).
- "confidence": your confidence from 0 to 1 that "character" is right.
If there are no people, return an empty list."""

def describe(image_bgr, model=DEFAULT_MODEL, retry_empty=True):
    t0 = time.perf_counter()
    ask = _ask_ollama if ":" in model else _ask_nvidia if "/" in model else _ask_claude
    jpg = encode(image_bgr)                 # longest side scaled to 640 px
    result = _parse(ask(jpg, model))
    if not result["people"] and retry_empty:
        result = _parse(ask(jpg, model))     # reasoning models sometimes answer "nobody" too fast
    return result, time.perf_counter() - t0
```

**Making it robust:**

- **Tolerant JSON parser.** The reasoning model sometimes returned a bare list, repeated the JSON, or cut it off. `_parse` scans the text with `json.JSONDecoder.raw_decode` and collects every complete, de-duplicated person object.
- **Hedged requests.** The free hosted endpoint occasionally hangs. If no valid answer arrives within 15 s, a second request is launched in parallel without cancelling the first, up to 3 attempts. The first good answer wins.
- **Content rules built in.** The line-writing prompt forbids weapons, violence and personal insults, so the comments stay within the competition rules.

**Benchmark** (`benchmark.py`, 18 Creative Commons photos from Wikimedia, with credits in `credits.json`; only the `character` field counts as a hit):

| Model | Correct | Time per photo |
|---|---|---|
| Qwen3-VL 2B, local (Ollama, GTX 1650 4 GB) | 15/18 | ~18 s |
| NVIDIA Nemotron 3 Nano Omni 30B-A3B (hosted) | 15/18 | 1–3 s per person |
| Llama 3.2 Vision | — | not usable in the EU (licence) |

Both models scored the same, so the local model is as accurate; it is just slower on a laptop GPU. That is why the backend is a one-word switch: with `--model qwen3-vl:2b-instruct` the recognition itself runs locally. At the party we used the hosted model for speed.

**Party extras:** `roulette.py` spins a roulette over the recognised guests and the skull announces who has to do a dare. `game.py` is a pygame show mode: guests fly into cards, the cards flip when the costume is recognised, and the skull introduces each one ("Victim number one: the hooded one.") with subtitles and procedurally generated Halloween music.

```bash
cd vision
python person_costume.py --camera 0 --speak                         # live camera, skull comments on each costume
python person_costume.py --camera 0 --speak --model qwen3-vl:2b-instruct   # local vision model
python costume_describer.py test_images/joker_2.jpg                 # single photo -> JSON
python benchmark.py qwen3-vl:2b-instruct nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
```

## Step 7 — Power

```
36 V battery -> F1 15 A -> main switch -> e-stop -> hoverboard boards
                                       \-> F2 5 A -> DC-DC 60 V->12 V 10 A -> 12 V rail (1000 uF)
                                              |-> F5 5 A -> Jetson (barrel jack)
                                              |-> F3 3 A -> XL4015 -> 5 V pan servo
                                              \-> F4 3 A -> XL4015 -> 5 V tilt servo
```

- Measured: the Jetson draws a **1.7 A peak at 12 V** with the agent running and **~2 A** with camera, eye controller and speaker attached (~24 W).
- Everything that sees battery voltage (up to 42 V when charged) must be **DC-rated ≥ 48 V**. Ordinary car blade fuses are only rated 32 V; I used mini blade fuses rated 58 V DC.
- All grounds are common. Wire gauges: 14 AWG on 36 V, 16 AWG on 12 V, 18 AWG to the servos.

## Step 8 — Putting it together

- Jetson USB-A ports: C922, eye ESP32, neck ESP32. A powered hub carries the USB audio adapter. Since both ESP32s use the same USB chip, use `/dev/serial/by-path/...` names and always plug each one into the same port.
- Start the agent with `python voice_agent.py --eyes <port> --neck <port>`. The skull falls asleep with its head down, wakes up, performs the intro and starts listening.
- `tools/head_control.py` is a small web panel (http://localhost:8080) to test eyes, moods, LEDs and neck by hand.

## How it fits the Halloween theme

- **The monster:** a skull possessed by an AI — a modern twist on the haunted object.
- **The horror trope:** the "awakening", where the thing realises it is alive and that *you* are there.
- **The theatre:** bloodshot eyes, a heartbeat glowing through the plastic, a growling voice and a head that turns to stare at you.
- **The party test:** on Halloween night (31 October) I ran the costume module at a party with friends. The skull looked at each guest, named their costume and made a sarcastic comment about it, and if someone came without a costume it mocked them for that too.

## Results and numbers

| Metric | Value |
|---|---|
| Time from end of question to voice | 3.8–5.9 s (filler line at 1.5 s) |
| LLM speed (qwen3:4b-instruct, GPU) | ~17 tokens/s |
| Whisper base (CPU int8) | ~2.2 s per utterance |
| Free RAM with everything loaded | ~2.4 GB of 8 GB |
| Jetson power | ~24 W (2 A at 12 V) |
| Continuous test (Jetson) | wake-up intro + 7 conversation turns without failures |
| Costume recognition (18 test photos) | 15/18 correct (Nemotron API 1–3 s per person; Qwen3-VL 2B local ~18 s) |

## What I would do next

- Close the loop between camera and neck: the YOLO person boxes already exist, so the next step is sending their position as `L x y` (eyes) and `P`/`T` (neck) so the skull follows you continuously.
- A faster fully offline costume recogniser on the Jetson (a CLIP-style model to name the costume instantly, plus the small local VLM for the description).
- Move the right hoverboard board to its second UART and drive both wheels again.
- PID speed control on the hoverboard (`DRIVING_MODE 1`) so both wheels match under load.

## Files

All code, firmware, CAD (STEP/STL) and schematics: **https://github.com/lemillion789/Halloween-Hackathon** (author: [github.com/lemillion789](https://github.com/lemillion789))

- `firmware/eyes/` — eye controller (ESP32 + 2x ST7735 + LEDs + IMU)
- `firmware/neck/` — neck servos, hoverboard UART, sonar, e-stop, relays
- `vision/voice_agent.py`, `personas.py`, `tts.py`, `memory.py` — the offline voice agent
- `vision/costume_describer.py`, `person_costume.py`, `skull_lines.py`, `roulette.py`, `game.py`, `benchmark.py` — costume recognition and party game
- `Hoverboard/` — firmware patch, flashed binaries and bench sketches
- `CAD/` — eye mount, neck, retainer (Python/CadQuery scripts and STEP/STL files)
- `schematics/` — wiring (WireViz), power, USB map, hoverboard pinout
