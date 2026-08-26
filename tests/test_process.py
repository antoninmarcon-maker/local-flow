"""Self-check des chemins de _process : silence, texte vide, garde de focus.

Aucune permission macOS ni modele requis : transcribe/paste/clipboard/frontmost
sont remplaces par des doublures. Usage : uv run python tests/test_process.py
"""

import io
import logging

import numpy as np

import localflow.app as app_mod
from localflow.app import App, Config

SR = app_mod.SAMPLE_RATE


class Doublures:
    """vad_parle : True -> le VAD est double et repond "parole" (les signaux de
    test sont des sinus, que le vrai Silero rejette a juste titre) ; False ->
    le vrai VAD tourne (bruit plat, silence...)."""

    def __init__(self, transcript: str, focus_change: bool, vad_parle: bool = True) -> None:
        self.pasted: list[str] = []
        self.clipboard: list[str] = []
        self._transcript = transcript
        self._vad_parle = vad_parle
        self._fronts = iter([(2, "Autre")] if focus_change else [(1, "Notes")])

    def install(self) -> None:
        app_mod.transcribe = lambda audio, model, language: self._transcript
        app_mod.paste = lambda text, kb: self.pasted.append(text)
        app_mod.clipboard_set = self.clipboard.append
        app_mod.frontmost_app = lambda: next(self._fronts)
        if self._vad_parle:
            app_mod.speech_stats = lambda audio: (0.9, 40)


ORIG = (app_mod.transcribe, app_mod.paste, app_mod.clipboard_set,
        app_mod.frontmost_app, app_mod.speech_stats)


def restore() -> None:
    (app_mod.transcribe, app_mod.paste, app_mod.clipboard_set,
     app_mod.frontmost_app, app_mod.speech_stats) = ORIG


def run_process(transcript: str, audio: np.ndarray, focus_change: bool,
                vad_parle: bool = True) -> Doublures:
    doubles = Doublures(transcript, focus_change, vad_parle)
    doubles.install()
    try:
        app = App(Config(model="turbo", key_name="f8", language="fr"))
        app.settings.auto_register = False  # pas d'appels Accessibilite reels ici
        app._process(audio, target=(1, "Notes"))
    finally:
        restore()
    return doubles


def parole(gain: float = 0.1) -> np.ndarray:
    """Signal a dynamique de parole : bonds de ~150 ms separes de quasi-silence.
    Un sinus a enveloppe constante serait rejete comme bruit plat par la garde."""
    t = np.arange(SR) / SR
    envelope = (np.sin(2 * np.pi * 3.3 * t) > 0).astype(np.float32)
    return (gain * envelope * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def bruit_plat(rms: float = 0.002) -> np.ndarray:
    noise = np.random.default_rng(42).normal(size=SR).astype(np.float32)
    return noise * (rms / float(np.sqrt(np.mean(np.square(noise)))))


def test_silence_ignore() -> None:
    doubles = run_process("fantome", np.zeros(SR, dtype=np.float32), focus_change=False)
    assert doubles.pasted == [], doubles.pasted
    assert doubles.clipboard == [], doubles.clipboard


def test_bruit_plat_ignore() -> None:
    """Micro ouvert, personne ne parle : bruit rejete par le vrai VAD Silero,
    quel que soit son niveau (il est normalise avant la garde)."""
    doubles = run_process("fantome", bruit_plat(), focus_change=False, vad_parle=False)
    assert doubles.pasted == [], doubles.pasted


def test_parole_gain_bas_acceptee() -> None:
    """Regression 2026-07-11 : volume d'entree micro 38/100 -> RMS clip 0.0002-0.0019,
    l'ancien seuil absolu (0.005) avalait la dictee. La dynamique de la parole doit
    suffire, quel que soit le gain."""
    doubles = run_process("Bonjour le monde.", parole(gain=0.001), focus_change=False)
    assert doubles.pasted == ["Bonjour le monde."], doubles.pasted


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


def test_transcription_absente_des_logs() -> None:
    """Le texte dicté est une donnée privée : le journal peut confirmer le
    traitement, jamais recopier son contenu."""
    stream = io.StringIO()
    logger = logging.getLogger("localflow")
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        run_process("Secret medical tres sensible.", parole(), focus_change=False)
    finally:
        logger.removeHandler(handler)
    output = stream.getvalue()
    assert "transcription terminee" in output.lower(), output
    assert "Secret medical tres sensible" not in output, output


class FakeUI:
    """Doublure minimale du panneau : enregistre les etats affiches."""

    def __init__(self) -> None:
        self.finals: list[tuple[str, bool]] = []
        self.events: list[str] = []

    def show_recording(self) -> None: self.events.append("recording")
    def show_preview(self, text: str) -> None: self.events.append("preview")
    def show_working(self, message: str) -> None: self.events.append("working")
    def show_message(self, message: str, autohide: float = 5.0) -> None: self.events.append("message")
    def hide_panel(self) -> None: self.events.append("hide")
    def set_status(self, message: str) -> None: self.events.append("status")
    def show_final(self, text: str, pasted: bool, note: str | None = None,
                   register: str | None = None) -> None:
        self.finals.append((text, pasted))


class FakeAI:
    def __init__(self, result: str) -> None:
        self.result = result
        self.calls: list[tuple] = []

    def transform(self, task, text, lang=None, context="", profile=""):
        self.calls.append((task, text, lang))
        return self.result


def make_action_doubles(transcript: str, fronts) -> dict:
    """Installe des doublures pour les chemins d'action IA ; renvoie les journaux."""
    logs = {"pasted": [], "undone": [], "clipboard": []}
    app_mod.transcribe = lambda audio, model, language: transcript
    app_mod.paste = lambda text, kb: logs["pasted"].append(text)
    app_mod.press_undo = lambda kb: logs["undone"].append(True)
    app_mod.clipboard_set = logs["clipboard"].append
    app_mod.frontmost_app = fronts
    app_mod.speech_stats = lambda audio: (0.9, 40)
    return logs


ORIG_UNDO = app_mod.press_undo


def restore_actions() -> None:
    restore()
    app_mod.press_undo = ORIG_UNDO


def test_action_corrige_et_remplace() -> None:
    """Apres collage, une action IA annule (Cmd+Z) puis colle la version
    transformee si l'app cible est toujours au premier plan."""
    logs = make_action_doubles("Bonjour le monde.", lambda: (1, "Notes"))
    try:
        app = App(Config(model="turbo", key_name="f8", language="fr"))
        app.settings.auto_register = False
        app.ai = FakeAI("Bonjour le monde !")
        app._process(parole(), target=(1, "Notes"))
        assert logs["pasted"] == ["Bonjour le monde."], logs
        app._run_action("correct", None)
        assert logs["undone"] == [True], logs
        assert logs["pasted"] == ["Bonjour le monde.", "Bonjour le monde !"], logs
        assert app._last["text"] == "Bonjour le monde !" and app._last["pasted"]
    finally:
        restore_actions()


def test_action_app_changee_presse_papiers() -> None:
    """Si l'app a change entre le collage et l'action, le resultat va au
    presse-papiers, sans Cmd+Z aveugle dans la mauvaise app."""
    fronts = iter([(1, "Notes"), (2, "Autre")])
    logs = make_action_doubles("Bonjour.", lambda: next(fronts))
    try:
        app = App(Config(model="turbo", key_name="f8", language="fr"))
        app.settings.auto_register = False
        app.ai = FakeAI("Hello.")
        app._process(parole(), target=(1, "Notes"))
        assert logs["pasted"] == ["Bonjour."], logs
        app._run_action("translate", "en")
        assert logs["undone"] == [], logs
        assert logs["pasted"] == ["Bonjour."], logs
        assert logs["clipboard"] == ["Hello."], logs
    finally:
        restore_actions()


def test_apercu_avant_collage() -> None:
    """Mode 'valider avant de coller' : rien n'est colle tant que l'utilisateur
    n'a pas demande le collage depuis le panneau."""
    logs = make_action_doubles("Bonjour le monde.", lambda: (1, "Notes"))
    try:
        app = App(Config(model="turbo", key_name="f8", language="fr"))
        app.settings.auto_register = False
        app.ui = FakeUI()
        app.settings.preview_before_paste = True
        app._process(parole(), target=(1, "Notes"))
        assert logs["pasted"] == [], logs
        assert app.ui.finals == [("Bonjour le monde.", False)], app.ui.finals
        app._run_action("paste", None)
        assert logs["pasted"] == ["Bonjour le monde."], logs
        assert app.ui.finals[-1] == ("Bonjour le monde.", True), app.ui.finals
    finally:
        restore_actions()


if __name__ == "__main__":
    test_silence_ignore()
    test_bruit_plat_ignore()
    test_parole_gain_bas_acceptee()
    test_texte_vide_ignore()
    test_collage_focus_stable()
    test_focus_change_pas_de_collage_aveugle()
    test_transcription_absente_des_logs()
    test_action_corrige_et_remplace()
    test_action_app_changee_presse_papiers()
    test_apercu_avant_collage()
    print("OK : chemins _process (silence, bruit plat, gain bas, vide, collage, "
          "garde de focus, actions IA, apercu avant collage)")
