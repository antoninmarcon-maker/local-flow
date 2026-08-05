"""Self-check des habitudes d'ecriture : journal, profil, suggestions.

Tout passe par un dossier temporaire (aucune ecriture dans ~/.config).
Usage : uv run python tests/test_habits.py
"""

import tempfile
from pathlib import Path

import localflow.habits as habits_mod
from localflow.config import Settings
from localflow.habits import Habits


def make_habits(tmp: Path) -> Habits:
    habits_mod.HISTORY_PATH = tmp / "history.jsonl"
    habits_mod.SUGGESTIONS_PATH = tmp / "suggestions.txt"
    settings = Settings()
    settings.habits_enabled = True
    return Habits(settings)


def test_profil_vide_sans_donnees() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        h = make_habits(Path(tmp))
        assert h.profile_summary() == ""


def test_profil_tutoiement_court() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        h = make_habits(Path(tmp))
        for _ in range(6):
            h.record("Salut, tu viens ce soir chez Baptiste ?", "WhatsApp", "fr")
        h._profile = None
        profile = h.profile_summary()
        assert "tutoie" in profile, profile
        assert "courts" in profile, profile
        assert "Salut" in profile, profile
        assert "emojis" in profile, profile


def test_suggestions_noms_propres() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        h = make_habits(Path(tmp))
        for _ in range(5):
            h.record("On retrouve Baptiste au Hellfest avec Margaux.", "Messages", "fr")
        h._profile = None
        h.profile_summary()
        content = habits_mod.SUGGESTIONS_PATH.read_text(encoding="utf-8")
        assert "Baptiste" in content, content
        assert "Hellfest" in content, content
        assert "Margaux" in content, content


def test_desactive_n_ecrit_rien() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        h = make_habits(Path(tmp))
        h.settings.habits_enabled = False
        h.record("Du texte prive qui ne doit pas etre journalise.", "Notes", "fr")
        assert not habits_mod.HISTORY_PATH.exists()
        assert h.profile_summary() == ""


if __name__ == "__main__":
    test_profil_vide_sans_donnees()
    test_profil_tutoiement_court()
    test_suggestions_noms_propres()
    test_desactive_n_ecrit_rien()
    print("OK : habitudes (profil vide, tutoiement/court, suggestions, opt-out)")
