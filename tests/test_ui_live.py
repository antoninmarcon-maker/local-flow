"""Self-check UI en conditions reelles : vraie barre de menus, vrai panneau,
vrais boutons — pilotes par programme sur le run loop principal.

Verifie ce que les doublures ne peuvent pas verifier : la construction AppKit,
le threading (show_* depuis un thread de fond via callAfter), le cablage
bouton -> delegate -> App, et les toggles du menu. L'App est une doublure :
aucun collage, aucun micro. Un panneau apparait ~2 s a l'ecran.

Usage : uv run python tests/test_ui_live.py
"""

import os
import threading

import objc
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
from Foundation import NSObject, NSTimer
from PyObjCTools import AppHelper

import localflow.config as config_mod
from localflow.config import Settings
from localflow.ui import UI

RESULTS: dict = {"actions": [], "errors": []}


class FakeApp:
    def request_action(self, task, lang=None):
        RESULTS["actions"].append((task, lang))

    def request_paste_last(self):
        RESULTS["actions"].append(("paste", None))


class Script(NSObject):
    """Deroule le scenario par etapes sur le thread principal."""

    def initWithUI_(self, ui):
        self = objc.super(Script, self).init()
        self.ui = ui
        return self

    def step1_(self, _timer):
        # etats pousses depuis un thread de fond, comme le worker reel
        def worker():
            self.ui.show_recording()
            self.ui.show_preview("apercu en cours de dictee")
            self.ui.show_working("Transcription…")
            self.ui.show_final("Bonjour le monde.", pasted=True)
        threading.Thread(target=worker, daemon=True).start()
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0, self, "step2:", None, False)

    def step2_(self, _timer):
        try:
            panel = self.ui._panel
            assert panel.isVisible(), "panneau invisible apres show_final"
            assert self.ui._text_label.stringValue() == "Bonjour le monde.", \
                self.ui._text_label.stringValue()
            titles = [str(b.title()) for b in self.ui._buttons]
            assert titles == ["Corriger", "→ EN", "→ ES", "Pro", "Amical"], titles
            # clic simule sur chaque bouton : passe par le vrai delegate
            for b in self.ui._buttons:
                self.ui._delegate.buttonAction_(b)
            # panneau non-activant : il ne doit pas etre la fenetre cle
            assert not panel.isKeyWindow(), "le panneau a pris le focus"
            # toggle de menu : troisieme item = premiere case a cocher
            menu = self.ui._status_item.menu()
            toggle = menu.itemAtIndex_(2)
            before = self.ui.settings.live_preview
            self.ui._delegate.menuToggle_(toggle)
            assert self.ui.settings.live_preview == (not before), "toggle sans effet"
            self.ui._delegate.menuToggle_(toggle)  # restaure
            self.ui.hide_panel()
        except Exception as exc:  # noqa: BLE001
            RESULTS["errors"].append(repr(exc))
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.4, self, "finish:", None, False)

    def finish_(self, _timer):
        # ponytail: stopEventLoop termine le process : tout verifier ICI,
        # le code apres runEventLoop() ne s'execute jamais.
        try:
            assert not self.ui._panel.isVisible(), "panneau encore visible apres hide"
        except Exception as exc:  # noqa: BLE001
            RESULTS["errors"].append(repr(exc))
        expected = [("correct", None), ("translate", "en"), ("translate", "es"),
                    ("pro", None), ("friendly", None)]
        if RESULTS["actions"] != expected:
            RESULTS["errors"].append(f"actions inattendues : {RESULTS['actions']}")
        if RESULTS["errors"]:
            print("ECHEC :", RESULTS["errors"], flush=True)
            os._exit(1)
        print("OK : UI reelle (panneau non-activant, apercu, boutons -> actions, "
              "toggle menu, masquage)", flush=True)
        AppHelper.stopEventLoop()


def main() -> None:
    import tempfile

    tmp = tempfile.mkdtemp()
    config_mod.CONFIG_DIR = config_mod.SETTINGS_PATH.parent  # inchange pour lecture
    config_mod.SETTINGS_PATH = type(config_mod.SETTINGS_PATH)(tmp) / "settings.json"

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    settings = Settings()  # defauts : en + es
    ui = UI(settings, FakeApp())
    ui.setup()
    script = Script.alloc().initWithUI_(ui)
    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        0.2, script, "step1:", None, False)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
