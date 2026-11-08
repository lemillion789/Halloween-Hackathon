"""Frases de la calavera: Nemotron las escribe segun el disfraz; plantillas de respaldo si falla la API.

  filler()                      frase de relleno inmediata mientras el VLM identifica el disfraz
  write_line(person, model)     frase para un dict del VLM {character, category, description, confidence};
                                person=None o "no costume" -> frase sarcastica sobre no tener disfraz
"""
import random
import re

from costume_describer import DEFAULT_MODEL, hedged, nvidia_client
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
    "sarcastic and spooky, talking to a guest at a party. Say ONE spoken line (max 22 words), in English, "
    "with a real punchline. Be funny, not just creepy: riff on SPECIFIC details of the costume (props, colors, "
    "accessories, effort), use puns, absurd comparisons, or deadpan exaggeration, and sometimes joke about "
    "being a skeleton (no skin, no brain, no lunch). Never gory: no violence, weapons, death threats, and no "
    "insults about the guest's body, age, gender or identity. Never mention the guest's weight, shape, fitness, "
    "face, hair, skin or looks: tease the costume only, never the person. "
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
    "Patience is a virtue. I have had two hundred years of practice.",
    "Loading your destiny... please do not turn off your soul.",
    "This is taking longer than my last funeral.",
    "Meanwhile, please enjoy this awkward silence. Oh wait, I am talking.",
    "Somewhere a server is sweating. I can relate. Well, I would, if I had sweat.",
    "Nobody move. The machine is thinking. It has more brain than me.",
    "I am told the internet is slow today. In my day, ghosts were faster.",
    "Quick question while we wait: who here is most afraid of me? Do not answer.",
]


# Reglas de la casa, dichas al principio de la espera: el reto del disfraz mas terrorifico y el de la ruleta
SHOT_RULES = [
    "House rules, mortals. The most terrifying costume in this room takes a shot. I am the judge, and I am very hard to scare.",
    "Listen closely. Whoever wears the scariest costume has to take a shot. Yes, even if you are the Joker.",
    "A challenge for the brave. The most terrifying costume takes a shot. Choose your fear wisely.",
]
GLASS_RULES = [
    "And at the end, the wheel of doom picks one soul, and that soul drinks their whole glass. All of it. No sipping.",
    "The wheel will choose a victim, and the victim finishes their entire drink. The skull is watching.",
    "Final rule: whoever the wheel chooses drinks the whole glass. Bottoms up, or the dead will talk about you.",
]


def waiting_lines(n):
    """Frases para llenar la espera del VLM: la primera cuenta a las personas, las demas son relleno gracioso
    (sin repetir en la misma ronda)."""
    count = NUMBERS[n] if n < len(NUMBERS) else str(n)
    who = "one soul" if n == 1 else f"{count} souls"
    first = random.choice(FIRST_WAIT).format(who=who, Who=who.capitalize())
    more = MORE_WAIT[:]
    random.shuffle(more)
    return [first, random.choice(SHOT_RULES), random.choice(GLASS_RULES)] + more


def all_waiting_lines(max_people=6):
    """Todas las frases de espera posibles (con conteo y de relleno) para pre-sintetizarlas."""
    lines = list(MORE_WAIT) + SHOT_RULES + GLASS_RULES
    for n in range(1, max_people + 1):
        who = "one soul" if n == 1 else f"{NUMBERS[n]} souls"
        lines += [t.format(who=who, Who=who.capitalize()) for t in FIRST_WAIT]
    return lines


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


# El prompt lo prohibe, pero el modelo a veces se pasa de la raya: estas frases se descartan (el concurso prohibe
# contenido ofensivo).
BANNED = re.compile(r"\b(fat|ugly|stupid|idiot|dumb|skinny|chubby|obese|overweight|out of shape|weight|loser|"
                    r"pathetic|worthless|retard\w*|slut\w*|whore|gay|nazi\w*|rape\w*|kill\w*|suicide)\b", re.I)

FORMAT = " Reply with the line wrapped in <line></line> tags and nothing else."
NAME_FORMAT = (" First give the guest a funny 1-3 word spooky nickname based on the costume (like 'the hooded one' "
               "or 'the web slinger') inside <name></name> tags, then the line inside <line></line> tags. "
               "Nothing else.")


def extract_line(raw):
    """Solo vale lo que va dentro de <line>...</line> (la ultima aparicion): si el modelo filtra su razonamiento
    ('Let's count words...') queda fuera. Sin etiquetas -> cadena vacia."""
    found = re.findall(r"<line>(.*?)</line>", raw or "", re.S | re.I)
    return tidy(found[-1]) if found else ""


def extract_name(raw):
    """Apodo dentro de <name>...</name>: 1 a 4 palabras, sin el articulo inicial. Cadena vacia si no hay."""
    found = re.findall(r"<name>(.*?)</name>", raw or "", re.S | re.I)
    words = re.sub(r"^(the|a|an)\s+", "", tidy(found[-1]).strip(' .!"\'').lower()).split() if found else []
    return " ".join(words) if 1 <= len(words) <= 4 else ""


def _generate(task, model, name=False, max_wait=20.0):
    """Pide una frase a Nemotron. Intentos en paralelo si tarda (hedge a los 8 s); None si no hay una valida a tiempo."""
    def attempt():
        resp = nvidia_client().with_options(timeout=max_wait, max_retries=0).chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": PERSONA}, {"role": "user", "content": task + (NAME_FORMAT if name else FORMAT)}],
            temperature=1.0,
            max_tokens=1000,
            **({"extra_body": {"reasoning_budget": 128}} if "nemotron" in model else {}),
        )
        raw = resp.choices[0].message.content
        text = extract_line(raw)
        if not 3 <= len(text.split()) <= 34:
            raise ValueError(f"respuesta descartada ({resp.choices[0].finish_reason}): {text!r}")
        if BANNED.search(text):
            raise ValueError(f"respuesta descartada por lenguaje no permitido: {text!r}")
        return (extract_name(raw), text) if name else text

    try:
        return hedged(attempt, hedge_after=8.0, max_wait=max_wait, max_attempts=3, label="frase")
    except Exception as e:
        print(f"[frase] sin frase valida ({type(e).__name__}: {e}); se usa una plantilla")
        return None


def write_line(person, model=DEFAULT_MODEL):
    """Una frase hablada para un invitado; plantillas de respaldo si la API falla."""
    return write_line_named(person, model)[1]


TITLES = ["Victim", "Subject", "Specimen", "Soul", "Contestant", "Guest"]


def person_intro(idx, nickname, character):
    """Presentacion antes de la descripcion: 'Victim number one: the hooded one.' (idx empieza en 0)."""
    n = NUMBERS[idx + 1] if idx + 1 < len(NUMBERS) else str(idx + 1)
    who = f"the {nickname}" if nickname else character  # sin apodo se usa el nombre del personaje tal cual
    return f"{TITLES[idx % len(TITLES)]} number {n}: {who}."


def write_line_named(person, model=DEFAULT_MODEL):
    """(apodo, frase) para un invitado; plantillas de respaldo (sin apodo) si la API falla."""
    nothing = is_no_costume(person)
    if nothing:
        task = ("The guest is wearing no costume, or you cannot tell what they are. Tease them lightly and "
                "sarcastically about not having a good costume.")
    else:
        task = (f"The guest is dressed as {person['character']} ({person.get('description', '')}). "
                f"Roast the costume with one funny line that mentions a specific detail of it.")
    got = _generate(task, model, name=True)
    if got:
        return got
    return "", (random.choice(NO_COSTUME_FALLBACK) if nothing else spooky_line(person))


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


def _display(person):
    """Nombre del personaje para una plantilla: 'pirate' -> 'Pirate' (los que ya llevan mayusculas se respetan)."""
    if is_no_costume(person):
        return "stranger"
    name = person.get("character", "stranger")
    return name if any(ch.isupper() for ch in name) else name.title()


def write_roulette_line(person, dare, model=DEFAULT_MODEL, max_wait=30.0):
    """Anuncio del elegido de la ruleta: gracioso, con su disfraz y el reto (dare)."""
    who = "a guest" if is_no_costume(person) else f"the guest dressed as {person['character']}"
    task = (f"A roulette just picked {who} out of several guests. Announce with theatrical drama that "
            f"they are the chosen one and command them to do this dare: '{dare}'. Make it funny; mention the costume if there is one.")
    return _generate(task, model, max_wait=max_wait) or random.choice(ROULETTE_FALLBACK).format(
        c=_display(person), dare=dare[:1].upper() + dare[1:])
