"""Self-check des reglages persistants (dossier temporaire, rien dans ~/.config).

Usage : uv run python tests/test_settings.py
"""

import stat
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
        assert s.auto_register
        assert not s.read_context and not s.habits_enabled
        assert s.live_preview and not s.preview_before_paste


def test_sauvegarde_privee() -> None:
    """Une configuration peut révéler des préférences sensibles à un autre
    compte local : le dossier et le fichier doivent rester privés."""
    with tempfile.TemporaryDirectory() as tmp:
        in_tmp(Path(tmp) / "localflow")
        Settings().save()
        assert stat.S_IMODE(config_mod.CONFIG_DIR.stat().st_mode) == 0o700
        assert stat.S_IMODE(config_mod.SETTINGS_PATH.stat().st_mode) == 0o600


def test_ancienne_configuration_redemande_le_consentement() -> None:
    """Avant la version de consentement, ces options étaient actives par
    défaut : leur valeur historique ne prouve donc pas un choix explicite."""
    with tempfile.TemporaryDirectory() as tmp:
        in_tmp(Path(tmp) / "localflow")
        config_mod.CONFIG_DIR.mkdir(parents=True)
        config_mod.SETTINGS_PATH.write_text(
            '{"read_context": true, "habits_enabled": true}', encoding="utf-8"
        )
        settings = Settings.load()
        assert not settings.read_context
        assert not settings.habits_enabled
        settings.habits_enabled = True
        settings.save()
        assert Settings.load().habits_enabled


def test_types_invalides_ne_peuvent_pas_activer_une_option() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        in_tmp(Path(tmp) / "localflow")
        config_mod.CONFIG_DIR.mkdir(parents=True)
        config_mod.SETTINGS_PATH.write_text(
            '{"privacy_consent_version": 1, "read_context": "false", '
            '"habits_enabled": "false", "live_preview": "false"}',
            encoding="utf-8",
        )
        settings = Settings.load()
        assert not settings.read_context
        assert not settings.habits_enabled
        assert settings.live_preview
        config_mod.SETTINGS_PATH.write_text(
            '{"privacy_consent_version": true, "read_context": true}',
            encoding="utf-8",
        )
        assert not Settings.load().read_context


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
    test_sauvegarde_privee()
    test_ancienne_configuration_redemande_le_consentement()
    test_types_invalides_ne_peuvent_pas_activer_une_option()
    test_toggle_langue_et_persistance()
    test_fichier_corrompu_ignore()
    test_langue_inconnue_filtree()
    print("OK : reglages (defauts, toggle+persistance, corruption, filtrage)")
