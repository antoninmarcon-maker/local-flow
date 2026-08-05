"""Habitudes d'ecriture : journal local des dictees et profil de style.

Tout est stocke dans ~/.config/localflow/ (jamais envoye nulle part) :
- history.jsonl : une ligne par dictee (horodatage, app, langue, texte)
- suggestions-dictionnaire.txt : noms propres recurrents absents du
  dictionnaire personnel, a ajouter d'un geste

Le profil de style (tutoiement, emojis, longueur, formules d'ouverture) est
derive du journal et injecte dans les prompts du moteur IA pour que les
reformulations ressemblent a ce que l'utilisateur ecrit vraiment.
"""

import json
import re
import time
from collections import Counter

from localflow.config import HISTORY_PATH, SUGGESTIONS_PATH, Settings
from localflow.stt import load_dictionary

PROFILE_MIN_ENTRIES = 5     # en dessous, pas assez de signal pour un profil
PROFILE_WINDOW = 200        # dictees considerees (les plus recentes)
RECOMPUTE_EVERY = 10        # recalcul du profil toutes les N dictees

_TU = re.compile(r"\b(?:tu|te|toi|ton|ta|tes)\b|\bt'", re.IGNORECASE)
_VOUS = re.compile(r"\b(?:vous|votre|vos)\b", re.IGNORECASE)
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
_OPENERS = ("salut", "coucou", "hello", "hey", "bonjour", "bonsoir", "yo")
_PROPER = re.compile(r"(?<=[a-zàâçéèêëîïôûùüÿ,;:!?()'\" ])\s([A-ZÀÂÇÉÈÊËÎÏÔÛÙÜ][a-zàâçéèêëîïôûùüÿ]{2,})\b")


class Habits:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._profile: str | None = None
        self._since_recompute = 0

    def record(self, text: str, app_name: str, language: str | None) -> None:
        if not self.settings.habits_enabled:
            return
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "app": app_name,
                 "lang": language, "text": text}
        with HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._since_recompute += 1
        if self._since_recompute >= RECOMPUTE_EVERY:
            self._profile = None  # sera recalcule au prochain profile_summary()

    def _load_entries(self) -> list[dict]:
        try:
            lines = HISTORY_PATH.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        entries = []
        for line in lines[-PROFILE_WINDOW:]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict):  # `42` est du JSON valide mais pas une entree
                entries.append(entry)
        return entries

    def profile_summary(self) -> str:
        """Resume du style en une phrase, pour les prompts IA. Chaine vide si
        pas assez de donnees."""
        if not self.settings.habits_enabled:
            return ""
        if self._profile is None:
            self._profile = self._compute_profile()
            self._since_recompute = 0
        return self._profile

    def _compute_profile(self) -> str:
        entries = self._load_entries()
        texts = [e.get("text", "") for e in entries if e.get("text")]
        if len(texts) < PROFILE_MIN_ENTRIES:
            return ""
        traits: list[str] = []
        tu = sum(len(_TU.findall(t)) for t in texts)
        vous = sum(len(_VOUS.findall(t)) for t in texts)
        if tu + vous >= 5:
            if tu >= 2 * vous:
                traits.append("tutoie spontanement")
            elif vous >= 2 * tu:
                traits.append("vouvoie spontanement")
        emoji_msgs = sum(1 for t in texts if _EMOJI.search(t))
        if emoji_msgs >= len(texts) * 0.25:
            traits.append("utilise des emojis")
        else:
            traits.append("n'utilise pas d'emojis")
        words = sorted(len(t.split()) for t in texts)
        median = words[len(words) // 2]
        if median <= 15:
            traits.append(f"messages courts (~{median} mots)")
        elif median >= 40:
            traits.append(f"messages longs (~{median} mots)")
        openers = Counter()
        for t in texts:
            first = t.split()[0].lower().strip(",.!") if t.split() else ""
            if first in _OPENERS:
                openers[first] += 1
        if openers:
            top, n = openers.most_common(1)[0]
            if n >= 3:
                traits.append(f"commence souvent par « {top.capitalize()} »")
        self._write_dictionary_suggestions(texts)
        return ", ".join(traits)

    def _write_dictionary_suggestions(self, texts: list[str]) -> None:
        """Noms propres revenant >= 3 fois et absents du dictionnaire personnel :
        proposes dans un fichier a cote, jamais ajoutes d'office."""
        counts: Counter = Counter()
        for t in texts:
            counts.update(_PROPER.findall(" " + t))
        known = (load_dictionary() or "").lower()
        frequent = [w for w, n in counts.most_common(30)
                    if n >= 3 and w.lower() not in known]
        if not frequent:
            return
        SUGGESTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SUGGESTIONS_PATH.write_text(
            "# Noms propres recurrents dans vos dictees, absents du dictionnaire\n"
            "# personnel. Copier les lignes utiles dans dictionary.txt.\n"
            + "\n".join(frequent) + "\n",
            encoding="utf-8",
        )
