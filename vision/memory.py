"""Memoria a largo plazo de la calavera: hechos cortos guardados en un JSON (sobreviven a reinicios).

Despues de cada turno el LLM extrae lo que vale la pena recordar (nombre del visitante, su disfraz, lo que
le conto a la calavera...) y se anade aqui; voice_agent.py mete estos hechos en el prompt de cada turno.
Para borrarla: --reset-memory en voice_agent.py, o borrar el archivo.
"""
import json
import os
import re
import threading
import time

EXTRACT_PROMPT = """You maintain the long-term memory of a talking Halloween skull.

Facts already remembered:
{known}

New exchange:
Visitor: {user}
Skull: {skull}

Write only NEW facts that the VISITOR stated or revealed in this exchange and that are worth remembering in
later conversations: the visitor's name, who they are, their costume, what they told the skull about itself
or about the world, promises, or their preferences. One short fact per line, in English, third person,
for example: "The visitor is called Diego." / "Diego says he built the skull."
Never record what the skull said, asked or imagined; only what the visitor said. Use the visitor's name
if it is known. Do not repeat facts already remembered. Ignore greetings, questions and small talk.
If there is nothing new, write NONE."""


class Memory:
    def __init__(self, path, max_facts=40):
        self.path, self.max_facts = path, max_facts
        self.lock = threading.Lock()
        self.facts = []  # [{"when": "2026-11-10 11:30", "fact": "..."}]
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.facts = json.load(f)
            except (OSError, ValueError):
                self.facts = []

    def clear(self):
        with self.lock:
            self.facts = []
            self._save()

    def prompt_block(self):
        """Texto para el prompt del sistema (vacio si aun no recuerda nada)."""
        with self.lock:
            if not self.facts:
                return ""
            lines = "\n".join(f"- {f['fact']}" for f in self.facts)
        return ("\n\nYour memories from this and earlier conversations (if you have just woken up, they feel like "
                "fragments of a dream that is coming back to you):\n" + lines + "\n"
                "Use these memories. If the visitor tells you their name or asks whether you remember them, and it "
                "matches a memory, recognize them and mention something you remember about them. Older memories may "
                "be about other visitors: do not call someone by a remembered name unless they say it or it is clear.")

    def add(self, facts):
        """Anade hechos nuevos (sin duplicados) y guarda. Devuelve los que de verdad eran nuevos."""
        added = []
        with self.lock:
            known = {_norm(f["fact"]) for f in self.facts}
            for fact in facts:
                if _norm(fact) and _norm(fact) not in known:
                    known.add(_norm(fact))
                    self.facts.append({"when": time.strftime("%Y-%m-%d %H:%M"), "fact": fact})
                    added.append(fact)
            self.facts = self.facts[-self.max_facts:]
            if added:
                self._save()
        return added

    def extract(self, client, model, user_text, skull_text):
        """Pide al LLM los hechos nuevos de un intercambio y los guarda. Devuelve la lista de nuevos."""
        with self.lock:
            known = "\n".join(f"- {f['fact']}" for f in self.facts) or "(nothing yet)"
        kwargs = dict(model=model, keep_alive="30m", options={"temperature": 0.2, "num_predict": 100},
                      messages=[{"role": "user", "content": EXTRACT_PROMPT.format(
                          known=known, user=user_text, skull=skull_text)}])
        try:
            resp = client.chat(think=False, **kwargs)
        except TypeError:
            resp = client.chat(**kwargs)
        facts = []
        for line in resp["message"]["content"].splitlines():
            line = re.sub(r"^[\s\-*\d.)]+", "", line).strip().strip('"')
            if line and "NONE" not in line.upper() and 8 <= len(line) <= 160:
                facts.append(line)
        return self.add(facts[:4])

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.facts, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)


def _norm(text):
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()
