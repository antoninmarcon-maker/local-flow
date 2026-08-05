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


def to_mp3(src: Path) -> Path:
    """Le micro passe en memoire dans l'app ; le mp3 verifie le chemin fichier
    (ffmpeg) de bout en bout, avec la perte de compression d'un vrai fichier."""
    dst = src.with_suffix(".mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                    "-codec:a", "libmp3lame", "-qscale:a", "4", str(dst)], check=True)
    return dst


def first_voice(*names: str) -> str | None:
    return next((v for v in names if voice_available(v)), None)


def test_transcription() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        en = Path(tmp) / "en.aiff"
        say("Hello, this is a local dictation test.", en)
        check("EN", en, ["local", "dictation", "test"])
        check("EN mp3", to_mp3(en), ["local", "dictation", "test"])

        fr_voice = first_voice("Thomas", "Amélie", "Amelie")
        if fr_voice:
            fr = Path(tmp) / "fr.aiff"
            say("Bonjour, ceci est un test de dictée vocale locale.", fr, fr_voice)
            check("FR", fr, ["test", "vocale", "locale"])
            check("FR mp3", to_mp3(fr), ["test", "vocale", "locale"])
        else:
            print("  FR : aucune voix francaise installee, test FR saute")

        es_voice = first_voice("Mónica", "Monica", "Paulina")
        if es_voice:
            es = Path(tmp) / "es.aiff"
            say("Hola, esta es una prueba de dictado por voz.", es, es_voice)
            check("ES", es, ["prueba", "voz"])
        else:
            print("  ES : aucune voix espagnole installee, test ES saute")


if __name__ == "__main__":
    print(f"Self-check local-flow, modele : {MODEL}")
    test_clean()
    print("  clean() : OK")
    test_transcription()
    print("OK")
