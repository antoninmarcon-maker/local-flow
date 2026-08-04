"""Presse-papiers et collage par Cmd+V simule."""

import subprocess
import time

from pynput import keyboard


def clipboard_get() -> str:
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout


def clipboard_set(text: str) -> None:
    subprocess.run(["pbcopy"], input=text, text=True, check=True)


def paste(text: str, kb: keyboard.Controller) -> None:
    """Colle via presse-papiers + Cmd+V simule, puis restaure le presse-papiers.

    ponytail: restauration texte seulement ; une image copiee juste avant est
    perdue. Et la restauration est CONDITIONNELLE : une app cible chargee peut
    lire le pasteboard apres notre delai (elle collerait l'ancien contenu), et
    l'utilisateur peut re-copier autre chose entre-temps (on ecraserait sa
    copie). On ne restaure que si le presse-papiers contient encore exactement
    le texte colle ; le delai d'1 s ne coute rien de percu (thread de fond,
    le texte est deja colle)."""
    saved = clipboard_get()
    clipboard_set(text)
    time.sleep(0.05)
    with kb.pressed(keyboard.Key.cmd):
        kb.press("v")
        kb.release("v")
    time.sleep(1.0)
    if saved and clipboard_get() == text:
        clipboard_set(saved)


def press_undo(kb: keyboard.Controller) -> None:
    """Cmd+Z : utilise pour remplacer un collage precedent par sa version
    transformee (l'insertion collee est une etape d'annulation dans la
    quasi-totalite des apps)."""
    with kb.pressed(keyboard.Key.cmd):
        kb.press("z")
        kb.release("z")
    time.sleep(0.15)  # laisse l'app appliquer l'annulation avant le re-collage
