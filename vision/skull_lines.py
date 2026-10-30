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


def write_line(person, model=DEFAULT_MODEL):
    """Una frase hablada. Cualquier fallo de la API (sin internet, 429, respuesta vacia) usa plantillas."""
    nothing = is_no_costume(person)
    if nothing:
        task = ("The guest is wearing no costume, or you cannot tell what they are. Tease them lightly and "
                "sarcastically about not having a good costume.")
    else:
        task = (f"The guest is dressed as {person['character']} ({person.get('description', '')}). "
                f"Greet them in character as the skull, mentioning the costume with a witty or ominous comment.")
    try:
        resp = nvidia_client().with_options(timeout=20, max_retries=0).chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": PERSONA}, {"role": "user", "content": task}],
            temperature=0.9,
            max_tokens=400,
            **({"extra_body": {"reasoning_budget": 128}} if "nemotron" in model else {}),
        )
        text = re.sub(r'^["\'\s]+|["\'\s]+$', "", (resp.choices[0].message.content or "").strip())
        if 3 <= len(text.split()) <= 45:
            return text
    except Exception as e:
        print(f"[frase] error {type(e).__name__}: {e}")
    return random.choice(NO_COSTUME_FALLBACK) if nothing else spooky_line(person)
