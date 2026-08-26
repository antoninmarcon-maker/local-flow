"""Self-check de la migration des anciennes permissions locales."""

import stat
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import localflow.ai as ai_mod
import localflow.config as config_mod
import localflow.stt as stt_mod
from localflow.ai import AIEngine
from localflow.config import Settings


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_chargement_corrige_anciennes_permissions() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "localflow"
        directory.mkdir(mode=0o755)
        settings_path = directory / "settings.json"
        settings_path.write_text("{}", encoding="utf-8")
        settings_path.chmod(0o644)
        history_path = directory / "history.jsonl"
        history_path.write_text('{"text":"secret"}\n', encoding="utf-8")
        history_path.chmod(0o644)
        suggestions_path = directory / "suggestions-dictionnaire.txt"
        suggestions_path.write_text("NomSecret\n", encoding="utf-8")
        suggestions_path.chmod(0o644)
        shim_dir = directory / "bin"
        shim_dir.mkdir(mode=0o755)
        shim_path = shim_dir / "afmshim-legacy"
        shim_path.write_bytes(b"binary")
        shim_path.chmod(0o755)
        with patch.object(config_mod, "CONFIG_DIR", directory), patch.object(
            config_mod, "SETTINGS_PATH", settings_path
        ):
            Settings.load()
        assert mode(directory) == 0o700
        assert mode(settings_path) == 0o600
        assert mode(history_path) == 0o600
        assert mode(suggestions_path) == 0o600
        assert mode(shim_dir) == 0o700
        assert mode(shim_path) == 0o700


def test_dictionnaire_existant_devient_prive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "localflow"
        directory.mkdir(mode=0o755)
        dictionary = directory / "dictionary.txt"
        dictionary.write_text("Baptiste\n", encoding="utf-8")
        dictionary.chmod(0o644)
        with patch.object(stt_mod, "DICTIONARY_PATH", dictionary):
            assert stt_mod.load_dictionary() == "Vocabulaire : Baptiste."
        assert mode(directory) == 0o700
        assert mode(dictionary) == 0o600


def test_shim_compile_est_reserve_au_compte() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "afmshim.swift"
        source.write_text("// shim", encoding="utf-8")
        shim_dir = root / "bin"

        def fake_compile(args, **_kwargs):
            output = Path(args[args.index("-o") + 1])
            output.write_bytes(b"binary")
            return SimpleNamespace(returncode=0, stderr="")

        with (
            patch.object(ai_mod, "SHIM_SOURCE", source),
            patch.object(ai_mod, "SHIM_DIR", shim_dir),
            patch.object(ai_mod.shutil, "which", return_value="/usr/bin/swiftc"),
            patch.object(ai_mod.subprocess, "run", side_effect=fake_compile),
        ):
            binary = AIEngine()._ensure_shim()
        assert mode(shim_dir) == 0o700
        assert mode(binary) == 0o700


if __name__ == "__main__":
    test_chargement_corrige_anciennes_permissions()
    test_dictionnaire_existant_devient_prive()
    test_shim_compile_est_reserve_au_compte()
    print("OK : migration des permissions locales")
