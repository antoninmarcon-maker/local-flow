"""Self-check des reglages persistants (dossier temporaire, rien dans ~/.config).

Usage : uv run python tests/test_settings.py
"""

import tempfile
from pathlib import Path

import localflow.config as config_mod
from localflow.config import Settings


def in_tmp(tmp: Path) -> None:
    config_mod.CONFIG_DIR = tmp
    config_mod.SETTINGS_PATH = tmp / "settings.json"


def test_defauts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        in_tmp(Path(tmp))
        s = Settings.load()
        assert s.translate_langs == ["en", "es"], s.translate_langs
        assert s.auto_register and s.read_context and s.habits_enabled
        assert s.live_preview and not s.preview_before_paste


def test_toggle_langue_et_persistance() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        in_tmp(Path(tmp))
        s = Settings.load()
        s.toggle_lang("de")
        s.toggle_lang("en")
        assert s.translate_langs == ["es", "de"], s.translate_langs
        s2 = Settings.load()
        assert s2.translate_langs == ["es", "de"], s2.translate_langs
        s2.toggle_lang("en")  # re-coche : ordre canonique en, es, de
        assert s2.translate_langs == ["en", "es", "de"], s2.translate_langs


def test_fichier_corrompu_ignore() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        in_tmp(Path(tmp))
        config_mod.SETTINGS_PATH.write_text("{pas du json", encoding="utf-8")
        s = Settings.load()
        assert s.translate_langs == ["en", "es"]


def test_langue_inconnue_filtree() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        in_tmp(Path(tmp))
        config_mod.SETTINGS_PATH.write_text(
            '{"translate_langs": ["en", "klingon"]}', encoding="utf-8")
        s = Settings.load()
        assert s.translate_langs == ["en"], s.translate_langs


if __name__ == "__main__":
    test_defauts()
    test_toggle_langue_et_persistance()
    test_fichier_corrompu_ignore()
    test_langue_inconnue_filtree()
    print("OK : reglages (defauts, toggle+persistance, corruption, filtrage)")
