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
PRIVACY_CONSENT_VERSION = 1


def ensure_private_directory(path: Path) -> None:
    """Crée un dossier réservé au compte courant et corrige un ancien mode."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def secure_write_text(path: Path, content: str) -> None:
    """Écrit atomiquement un fichier privé, même avec un umask permissif."""
    ensure_private_directory(path.parent)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        tmp.unlink(missing_ok=True)


def migrate_private_storage_permissions() -> None:
    """Corrige les modes créés par les versions antérieures au démarrage."""
    if not CONFIG_DIR.exists():
        return
    ensure_private_directory(CONFIG_DIR)
    for name in (
        "settings.json",
        "dictionary.txt",
        "history.jsonl",
        "suggestions-dictionnaire.txt",
    ):
        path = CONFIG_DIR / name
        if path.is_file():
            path.chmod(0o600)
    shim_dir = CONFIG_DIR / "bin"
    if shim_dir.is_dir():
        ensure_private_directory(shim_dir)
        for path in shim_dir.glob("afmshim-*"):
            if path.is_file():
                path.chmod(0o700)

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
        from localflow.hotkey import (
            KEYS,  # import differe : evite Quartz a l'import de config
        )

        return KEYS[self.key_name]


@dataclass
class Settings:
    """Reglages persistants, modifiables depuis la barre de menus."""

    translate_langs: list[str] = field(default_factory=lambda: ["en", "es"])
    auto_register: bool = True        # ton pro/amical choisi selon l'app active
    read_context: bool = False        # opt-in : lire le fil visible via Accessibilite
    habits_enabled: bool = False      # opt-in : journal local des dictees + profil de style
    live_preview: bool = True         # apercu de transcription pendant la dictee
    preview_before_paste: bool = False  # ne pas coller automatiquement, valider dans le panneau
    privacy_consent_version: int = PRIVACY_CONSENT_VERSION

    @classmethod
    def load(cls) -> "Settings":
        try:
            migrate_private_storage_permissions()
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise TypeError("les reglages doivent etre un objet JSON")
            known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
            bool_fields = {
                "auto_register",
                "read_context",
                "habits_enabled",
                "live_preview",
                "preview_before_paste",
            }
            for field_name in bool_fields:
                if field_name in known and type(known[field_name]) is not bool:
                    known.pop(field_name)
            if not isinstance(known.get("translate_langs", []), list):
                known.pop("translate_langs", None)
            # Les anciennes versions sauvegardaient parfois `true` alors que
            # ces fonctions étaient actives par défaut. Seule une sauvegarde
            # produite après l'introduction de ce marqueur vaut consentement.
            consent_version = data.get("privacy_consent_version")
            if (type(consent_version) is not int
                    or consent_version != PRIVACY_CONSENT_VERSION):
                known["read_context"] = False
                known["habits_enabled"] = False
            known["privacy_consent_version"] = PRIVACY_CONSENT_VERSION
            settings = cls(**known)
            settings.translate_langs = [c for c in settings.translate_langs
                                        if c in TRANSLATE_LANGS]
        except (FileNotFoundError, json.JSONDecodeError, TypeError, AttributeError):
            # fichier absent, corrompu, ou types invalides : retour aux defauts
            return cls()
        return settings

    def save(self) -> None:
        secure_write_text(
            SETTINGS_PATH,
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
        )

    def toggle_lang(self, code: str) -> None:
        if code in self.translate_langs:
            self.translate_langs = [c for c in self.translate_langs if c != code]
        else:
            # conserve l'ordre canonique de TRANSLATE_LANGS
            enabled = set(self.translate_langs) | {code}
            self.translate_langs = [c for c in TRANSLATE_LANGS if c in enabled]
        self.save()
