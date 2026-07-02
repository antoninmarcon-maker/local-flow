"""Self-check runnable : genere de la parole avec `say`, transcrit, verifie le texte.

Usage : uv run python tests/test_pipeline.py [modele]
Le modele est telecharge au premier appel (ensuite tout est offline).
Le decodage du fichier audio de test passe par ffmpeg ; l'app en usage reel
n'en a pas besoin (audio micro passe en memoire).
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

from localflow.app import clean, transcribe

MODEL = sys.argv[1] if len(sys.argv) > 1 else "turbo"


def say(text: str, path: Path, voice: str | None = None) -> None:
    cmd = ["say", "-o", str(path)]
    if voice:
        cmd += ["-v", voice]
    subprocess.run(cmd + [text], check=True)


def voice_available(name: str) -> bool:
    out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    return any(line.split()[0] == name for line in out.splitlines() if line.strip())


def check(label: str, path: Path, expected_words: list[str]) -> None:
    t0 = time.monotonic()
    text = clean(transcribe(str(path), MODEL, None))
    elapsed = time.monotonic() - t0
    print(f"  {label} ({elapsed:.1f}s) : {text!r}")
    lower = text.lower()
    missing = [w for w in expected_words if w not in lower]
    assert not missing, f"{label} : mots absents de la transcription : {missing}"


def test_clean() -> None:
    assert clean("Euh, bonjour hum le monde.") == "bonjour le monde."
    assert clean("  Deux   espaces. ") == "Deux espaces."


def test_transcription() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        en = Path(tmp) / "en.aiff"
        say("Hello, this is a local dictation test.", en)
        check("EN", en, ["local", "dictation", "test"])

        for voice in ("Thomas", "Amélie", "Amelie"):
            if voice_available(voice):
                fr = Path(tmp) / "fr.aiff"
                say("Bonjour, ceci est un test de dictée vocale locale.", fr, voice)
                check("FR", fr, ["test", "vocale", "locale"])
                break
        else:
            print("  FR : aucune voix francaise installee, test FR saute")


if __name__ == "__main__":
    print(f"Self-check local-flow, modele : {MODEL}")
    test_clean()
    print("  clean() : OK")
    test_transcription()
    print("OK")
