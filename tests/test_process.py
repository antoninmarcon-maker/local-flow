"""Self-check des chemins de _process : silence, texte vide, garde de focus.

Aucune permission macOS ni modele requis : transcribe/paste/clipboard/frontmost
sont remplaces par des doublures. Usage : uv run python tests/test_process.py
"""

import numpy as np

import localflow.app as app_mod
from localflow.app import App, Config

SR = app_mod.SAMPLE_RATE


class Doublures:
    def __init__(self, transcript: str, focus_change: bool) -> None:
        self.pasted: list[str] = []
        self.clipboard: list[str] = []
        self._transcript = transcript
        self._fronts = iter([(2, "Autre")] if focus_change else [(1, "Notes")])

    def install(self) -> None:
        app_mod.transcribe = lambda audio, model, language: self._transcript
        app_mod.paste = lambda text, kb: self.pasted.append(text)
        app_mod.clipboard_set = self.clipboard.append
        app_mod.frontmost_app = lambda: next(self._fronts)


ORIG = (app_mod.transcribe, app_mod.paste, app_mod.clipboard_set, app_mod.frontmost_app)


def restore() -> None:
    app_mod.transcribe, app_mod.paste, app_mod.clipboard_set, app_mod.frontmost_app = ORIG


def run_process(transcript: str, audio: np.ndarray, focus_change: bool) -> Doublures:
    doubles = Doublures(transcript, focus_change)
    doubles.install()
    try:
        app = App(Config(model="turbo", key_name="f8", language="fr"))
        app._process(audio, target=(1, "Notes"))
    finally:
        restore()
    return doubles


def parole() -> np.ndarray:
    return (0.1 * np.sin(np.linspace(0, 440, SR))).astype(np.float32)


def test_silence_ignore() -> None:
    doubles = run_process("fantome", np.zeros(SR, dtype=np.float32), focus_change=False)
    assert doubles.pasted == [], doubles.pasted
    assert doubles.clipboard == [], doubles.clipboard


def test_texte_vide_ignore() -> None:
    doubles = run_process("   ", parole(), focus_change=False)
    assert doubles.pasted == [], doubles.pasted


def test_collage_focus_stable() -> None:
    doubles = run_process("Bonjour le monde.", parole(), focus_change=False)
    assert doubles.pasted == ["Bonjour le monde."], doubles.pasted
    assert doubles.clipboard == [], doubles.clipboard


def test_focus_change_pas_de_collage_aveugle() -> None:
    doubles = run_process("Bonjour le monde.", parole(), focus_change=True)
    assert doubles.pasted == [], doubles.pasted
    assert doubles.clipboard == ["Bonjour le monde."], doubles.clipboard


if __name__ == "__main__":
    test_silence_ignore()
    test_texte_vide_ignore()
    test_collage_focus_stable()
    test_focus_change_pas_de_collage_aveugle()
    print("OK : chemins _process (silence, vide, collage, garde de focus)")
