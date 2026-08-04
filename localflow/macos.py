"""Petites integrations macOS : sons, app active, volume d'entree micro."""

import subprocess
import time

from AppKit import NSSound, NSWorkspace

# ponytail: afplay mettait ~0,9 s a initialiser AudioToolbox avant de jouer --
# le "Tink" cense dire "tu peux parler" arrivait apres le debut de la parole.
# NSSound precharge part quasi instantanement, sans spawn de process.
_sounds: dict[str, NSSound] = {}


def preload_sounds(*names: str) -> None:
    for name in names:
        sound = NSSound.soundNamed_(name)
        if sound is not None:
            _sounds[name] = sound


def play_sound(name: str) -> None:
    sound = _sounds.get(name) or NSSound.soundNamed_(name)
    if sound is None:  # nom inconnu : repli sur afplay, sans bloquer
        subprocess.Popen(
            ["afplay", f"/System/Library/Sounds/{name}.aiff"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return
    _sounds[name] = sound
    if sound.isPlaying():
        sound.stop()
    sound.play()


def ts() -> str:
    return time.strftime("%H:%M:%S")


def frontmost_app() -> tuple[int, str]:
    """(pid, nom) de l'app active. La transcription pouvant prendre plusieurs
    secondes sous pression memoire, l'app active au collage n'est pas forcement
    celle de la dictee : on capture la cible au relachement pour comparer."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return (0, "?")
    return (int(app.processIdentifier()), str(app.localizedName()))


def input_volume() -> int | None:
    try:
        out = subprocess.run(
            ["osascript", "-e", "input volume of (get volume settings)"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return int(out)
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return None
