"""Configuration CLI et reglages persistants (~/.config/localflow/settings.json)."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "localflow"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
DICTIONARY_PATH = CONFIG_DIR / "dictionary.txt"
HISTORY_PATH = CONFIG_DIR / "history.jsonl"
SUGGESTIONS_PATH = CONFIG_DIR / "suggestions-dictionnaire.txt"
SHIM_DIR = CONFIG_DIR / "bin"

# Langues proposees pour la traduction (cochables dans la barre de menus).
TRANSLATE_LANGS = {
    "en": "Anglais",
    "es": "Espagnol",
    "de": "Allemand",
    "it": "Italien",
    "pt": "Portugais",
}


@dataclass
class Config:
    """Options de lancement (ligne de commande)."""

    model: str
    key_name: str
    language: str | None
    use_ui: bool = True

    @property
    def pynput_key(self):
        from localflow.hotkey import KEYS  # import differe : evite Quartz a l'import de config

        return KEYS[self.key_name]


@dataclass
class Settings:
    """Reglages persistants, modifiables depuis la barre de menus."""

    translate_langs: list[str] = field(default_factory=lambda: ["en", "es"])
    auto_register: bool = True        # ton pro/amical choisi selon l'app active
    read_context: bool = True         # lire le fil de conversation visible (Accessibilite)
    habits_enabled: bool = True       # journal local des dictees + profil de style
    live_preview: bool = True         # apercu de transcription pendant la dictee
    preview_before_paste: bool = False  # ne pas coller automatiquement, valider dans le panneau

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
            settings = cls(**known)
            settings.translate_langs = [c for c in settings.translate_langs
                                        if c in TRANSLATE_LANGS]
        except (FileNotFoundError, json.JSONDecodeError, TypeError, AttributeError):
            # fichier absent, corrompu, ou types invalides : retour aux defauts
            return cls()
        return settings

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, SETTINGS_PATH)

    def toggle_lang(self, code: str) -> None:
        if code in self.translate_langs:
            self.translate_langs = [c for c in self.translate_langs if c != code]
        else:
            # conserve l'ordre canonique de TRANSLATE_LANGS
            enabled = set(self.translate_langs) | {code}
            self.translate_langs = [c for c in TRANSLATE_LANGS if c in enabled]
        self.save()
