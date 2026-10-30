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

PERSONA = (
    "You are a stand-up comedian trapped in an animatronic Halloween skull: dry British humor, theatrical, "
    "sarcastic and spooky, talking to a guest at a party. Say ONE spoken line (max 28 words), in English, "
    "with a real punchline. Be funny, not just creepy: riff on SPECIFIC details of the costume (props, colors, "
    "accessories, effort), use puns, absurd comparisons, or deadpan exaggeration, and sometimes joke about "
    "being a skeleton (no skin, no brain, no lunch). Never gory: no violence, weapons, death threats, and no "
    "insults about the guest's body, age, gender or identity; tease the costume, never the person. "
    "Do not copy these examples, they only show the tone: "
    "'Batman? Bold of you to sit down. I thought you only appeared when someone shined a light at a cloud.' / "
    "'A pirate, how brave. Tell me, do you also keep your treasure map under the couch cushions?' / "
    "'Spider-Man flashing a peace sign. The only superhero who also leads yoga classes.' "
    "Output only the line itself, no stage directions."
)


def filler():
    return random.choice(FILLERS)


NUMBERS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]

FIRST_WAIT = [
    "Let me see... I count {who} in this photo. Hold still while I judge your costumes.",
    "Ah, {who}. I have empty sockets for eyes and even I can see the effort. Or the lack of it.",
    "{Who} detected. Please do not move, I am developing my opinions.",
    "{Who}! Bold of you to enter my house. Now stay still while I stare at you.",
]

MORE_WAIT = [
    "Analyzing... this takes a while when you have no brain, only dust.",
    "Give me a second. Dead people are not known for their speed.",
    "Hmm, interesting... one of you is hiding something under that costume. Probably a sandwich.",
    "I would tap my fingers, but they fell off in eighteen twenty three.",
    "Almost there. Try to look scarier, the camera is watching.",
    "Still thinking... my brain is on vacation, but my jaw is on overtime.",
    "Do not worry, I only judge a little. Okay, a lot.",
]


def waiting_lines(n):
    """Frases para llenar la espera del VLM: la primera cuenta a las personas, las demas son relleno gracioso
    (sin repetir en la misma ronda)."""
    count = NUMBERS[n] if n < len(NUMBERS) else str(n)
    who = "one soul" if n == 1 else f"{count} souls"
    first = random.choice(FIRST_WAIT).format(who=who, Who=who.capitalize())
    more = MORE_WAIT[:]
    random.shuffle(more)
    return [first] + more


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


FORMAT = " Reply with the line wrapped in <line></line> tags and nothing else."


def extract_line(raw):
    """Solo vale lo que va dentro de <line>...</line> (la ultima aparicion): si el modelo filtra su razonamiento
    ('Let's count words...') queda fuera. Sin etiquetas -> cadena vacia."""
    found = re.findall(r"<line>(.*?)</line>", raw or "", re.S | re.I)
    return tidy(found[-1]) if found else ""


def _generate(task, model, attempts=2):
    """Pide una frase a Nemotron. Devuelve None si falla tras reintentar (sin internet, 429, vacia, fuera de rango)."""
    for attempt in range(attempts):
        try:
            resp = nvidia_client().with_options(timeout=20, max_retries=0).chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": PERSONA}, {"role": "user", "content": task + FORMAT}],
                temperature=1.0,
                max_tokens=1000,
                **({"extra_body": {"reasoning_budget": 128}} if "nemotron" in model else {}),
            )
            text = extract_line(resp.choices[0].message.content)
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
                f"Roast the costume with one funny line that mentions a specific detail of it.")
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
