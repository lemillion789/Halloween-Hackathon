"""Frases de la calavera: Nemotron las escribe segun el disfraz; plantillas de respaldo si falla la API.

  filler()                      frase de relleno inmediata mientras el VLM identifica el disfraz
  write_line(person, model)     frase para un dict del VLM {character, category, description, confidence};
                                person=None o "no costume" -> frase sarcastica sobre no tener disfraz
"""
import random
import re

from costume_describer import DEFAULT_MODEL, nvidia_client
from tts import spooky_line

FILLERS = [
    "Hmm... what do we have here...",
    "Ahh... fresh company. Let me take a look at you...",
    "Come closer... let me see what you are...",
    "Oh... someone is brave tonight...",
    "Interesting... hold still while I look into your soul...",
]

NO_COSTUME_FALLBACK = [
    "No costume? How brave. Or lazy. Probably lazy.",
    "I have been dead for two hundred years and even I made more effort than you.",
    "Is that your costume? A human who forgot it was Halloween. Terrifying.",
    "No costume at all... the scariest thing here is the lack of effort.",
]

PERSONA = ("You are a creepy, theatrical and sarcastic animatronic Halloween skull with dark British humor, "
           "speaking to a guest at a party. Say ONE short spoken line (max 22 words), in English. "
           "Playful and spooky, never gory: no violence, weapons, death threats, or insults about the "
           "guest's body, age, gender or identity. Output only the line itself, no quotes, no stage directions.")


def filler():
    return random.choice(FILLERS)


def is_no_costume(person):
    return not person or person.get("character", "").lower() in ("", "no costume", "none") \
        or person.get("confidence", 1) < 0.3


def tidy(text):
    """Deja una sola frase limpia. Nemotron a veces repite la respuesta (separada por saltos de linea o pegada)."""
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    parts = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    text = parts[0] if parts else ""
    half = len(text) // 2
    if half > 10 and text[:half].strip() == text[half:].strip():
        text = text[:half].strip()
    return re.sub(r'^["\'\s]+|["\'\s]+$', "", text)


def _generate(task, model, attempts=2):
    """Pide una frase a Nemotron. Devuelve None si falla tras reintentar (sin internet, 429, vacia, fuera de rango)."""
    for attempt in range(attempts):
        try:
            resp = nvidia_client().with_options(timeout=20, max_retries=0).chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": PERSONA}, {"role": "user", "content": task}],
                temperature=0.9,
                max_tokens=1000,
                **({"extra_body": {"reasoning_budget": 128}} if "nemotron" in model else {}),
            )
            text = tidy(resp.choices[0].message.content or "")
            if 3 <= len(text.split()) <= 45:
                return text
            print(f"[frase] respuesta descartada ({resp.choices[0].finish_reason}, intento {attempt + 1}): {text!r}")
        except Exception as e:
            print(f"[frase] error {type(e).__name__}: {e}")
    return None


def write_line(person, model=DEFAULT_MODEL):
    """Una frase hablada para un invitado; plantillas de respaldo si la API falla."""
    nothing = is_no_costume(person)
    if nothing:
        task = ("The guest is wearing no costume, or you cannot tell what they are. Tease them lightly and "
                "sarcastically about not having a good costume.")
    else:
        task = (f"The guest is dressed as {person['character']} ({person.get('description', '')}). "
                f"Greet them in character as the skull, mentioning the costume with a witty or ominous comment.")
    return _generate(task, model) or (random.choice(NO_COSTUME_FALLBACK) if nothing else spooky_line(person))


ROULETTE_INTROS = [
    "The wheel of doom has been summoned... someone in this room is about to suffer.",
    "Let the bones decide... who will it be...",
    "Round and round the wheel goes... and where it stops, nobody knows.",
]

ROULETTE_FALLBACK = [
    "The wheel has spoken! {c}, it is you! {dare}, and do not make me ask twice.",
    "Congratulations, {c}! The bones have chosen you. Now {dare}. Do it for the skull.",
]


def roulette_intro():
    return random.choice(ROULETTE_INTROS)


def write_roulette_line(person, dare, model=DEFAULT_MODEL):
    """Anuncio del elegido de la ruleta: gracioso, con su disfraz y el reto (dare)."""
    who = "a guest" if is_no_costume(person) else f"the guest dressed as {person['character']}"
    task = (f"A roulette just picked {who} out of several guests. Announce with theatrical drama that "
            f"they are the chosen one and command them to {dare}. Make it funny; mention the costume if there is one.")
    return _generate(task, model) or random.choice(ROULETTE_FALLBACK).format(
        c=person.get("character", "stranger") if not is_no_costume(person) else "stranger", dare=dare[:1].upper() + dare[1:])
