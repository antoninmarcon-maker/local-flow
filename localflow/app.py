"""local-flow : dictee vocale systeme entiere, 100 % locale.

Maintenir la touche configuree (fn par defaut, comme Wispr Flow) : le micro
enregistre. Relacher : transcription locale (mlx-whisper, GPU Metal) puis
collage du texte dans l'application active. Un panneau flottant affiche la
transcription en direct et propose corriger / traduire / reformuler via
Apple Intelligence (on-device). Aucune donnee ne quitte la machine.
"""

import argparse
import queue
import threading
import time

import numpy as np
from pynput import keyboard

from localflow.audio import (
    MIN_DURATION_S,
    SAMPLE_RATE,
    SILENCE_PEAK_RMS,
    SPEECH_DYNAMICS_RATIO,
    Recorder,
    normalize,
    speech_levels,
)
from localflow.clipboard import clipboard_set, paste, press_undo
from localflow.config import DICTIONARY_PATH, TRANSLATE_LANGS, Config, Settings
from localflow.context import read_conversation
from localflow.hotkey import FN_KEYCODE, KEYS, FnListener
from localflow.macos import frontmost_app, input_volume, play_sound, preload_sounds, ts
from localflow.stt import PREVIEW_MODEL, detect_language, load_dictionary, preload, transcribe
from localflow.textproc import clean
from localflow.vad import MIN_SPEECH_FRAMES, MIN_SPEECH_RATIO, speech_stats

ACTION_LABELS = {
    "correct": "Correction",
    "translate": "Traduction",
    "pro": "Reformulation pro",
    "friendly": "Reformulation amicale",
}


class App:
    def __init__(self, cfg: Config, settings: Settings | None = None,
                 ui=None, ai=None, habits=None) -> None:
        self.cfg = cfg
        self.settings = settings or Settings()
        self.ui = ui
        self.ai = ai
        self.habits = habits
        self.recorder = Recorder()
        self.kb = keyboard.Controller()
        self.recording = False
        self._pasting = threading.Event()
        self._jobs: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None
        self._detected_lang: str | None = None
        # derniere dictee : {"text": str, "target": (pid, nom), "pasted": bool}
        self._last: dict | None = None

    # ------------------------------------------------------------------ worker
    # Un unique thread consomme dictees et actions IA : deux transcriptions
    # concurrentes se ralentissaient mutuellement (GPU/GIL), l'ordre de collage
    # n'etait pas garanti, et deux paste() entrelaces corrompaient la
    # sauvegarde/restauration du presse-papiers.

    def _ensure_worker(self) -> None:
        if self._worker is None:
            self._worker = threading.Thread(target=self._drain, daemon=True)
            self._worker.start()

    def _drain(self) -> None:
        while True:
            kind, payload = self._jobs.get()
            try:
                if kind == "dictation":
                    self._process(*payload)
                elif kind == "action":
                    self._run_action(*payload)
            except Exception as exc:
                print(f"[erreur] {kind} : {exc}")
                if self.ui:
                    self.ui.show_message(f"Erreur : {exc}", autohide=6.0)
            finally:
                self._jobs.task_done()

    # --------------------------------------------------------- enregistrement

    def start_recording(self) -> None:
        if self.recording:
            return
        self.recording = True
        play_sound("Tink")
        self.recorder.start()
        if self.ui:
            self.ui.show_recording()
            if self.settings.live_preview:
                threading.Thread(target=self._preview_loop, daemon=True).start()

    def stop_recording(self) -> None:
        if not self.recording:
            return
        self.recording = False
        audio = self.recorder.stop()
        play_sound("Pop")
        if self.recorder.overflowed:
            print(f"[{ts()}] attention : blocs audio perdus pendant la capture "
                  "(machine tres chargee), la transcription peut etre trouee")
        duration = len(audio) / SAMPLE_RATE
        if duration < MIN_DURATION_S:
            print(f"[{ts()}] enregistrement trop court ({duration:.1f}s), ignore")
            if self.ui:
                self.ui.hide_panel()
            return
        target = frontmost_app()
        print(f"[{ts()}] {duration:.1f}s de parole, transcription en cours...")
        if self.ui:
            self.ui.show_working("Transcription…")
        self._ensure_worker()
        self._jobs.put(("dictation", (audio, target)))

    def cancel_recording(self) -> None:
        if not self.recording:
            return
        self.recording = False
        self.recorder.stop()
        play_sound("Bottle")
        print(f"[{ts()}] dictee annulee (autre touche pendant l'enregistrement)")
        if self.ui:
            self.ui.hide_panel()

    def on_press(self, key: object) -> None:
        if key == self.cfg.pynput_key:
            self.start_recording()

    def on_release(self, key: object) -> None:
        if key == self.cfg.pynput_key:
            self.stop_recording()

    # ----------------------------------------------------------- apercu direct

    def _preview_loop(self) -> None:
        """Toutes les ~1,2 s, transcrit l'audio accumule avec le petit modele
        et l'affiche dans le panneau. La passe finale reste turbo ; la langue
        detectee ici est reutilisee (economise la detection cote turbo)."""
        time.sleep(0.9)
        while self.recording:
            audio = self.recorder.snapshot()
            if len(audio) >= int(0.8 * SAMPLE_RATE):
                try:
                    audio = normalize(audio, speech_levels(audio)[1])
                    try:
                        _ratio, frames = speech_stats(audio)
                        heard = frames >= MIN_SPEECH_FRAMES
                    except Exception:
                        heard = True  # pas de VAD : on tente l'apercu quand meme
                    if heard:
                        if self.cfg.language is None and self._detected_lang is None:
                            self._detected_lang = detect_language(audio)
                        text = transcribe(audio, PREVIEW_MODEL,
                                          self.cfg.language or self._detected_lang)
                        if self.recording and text and self.ui:
                            self.ui.show_preview(text)
                except Exception:
                    return  # l'apercu ne doit jamais casser la dictee
            time.sleep(1.2)

    # ---------------------------------------------------------------- pipeline

    def _paste(self, text: str) -> None:
        """Collage avec garde : nos frappes synthetiques repassent par l'event
        tap fn et annulaient sinon la dictee suivante en cours (auto-sabotage)."""
        self._pasting.set()
        try:
            paste(text, self.kb)
        finally:
            self._pasting.clear()

    def _process(self, audio: np.ndarray, target: tuple[int, str]) -> None:
        floor, peak = speech_levels(audio)
        if peak < SILENCE_PEAK_RMS:
            print(f"[{ts()}] micro muet (crete RMS {peak:.6f}), ignore. Verifier "
                  "l'entree micro (Reglages Systeme > Son > Entree).")
            if self.ui:
                self.ui.show_message("Micro muet — verifier l'entree son", autohide=5.0)
            return
        audio = normalize(audio, peak)
        # Garde anti non-parole : VAD Silero sur l'audio normalise (le bruit
        # ambiant amplifie faisait halluciner Whisper avec confiance) ; repli
        # sur la dynamique de trames si onnxruntime manque.
        try:
            ratio, frames = speech_stats(audio)
            if frames < MIN_SPEECH_FRAMES or ratio < MIN_SPEECH_RATIO:
                print(f"[{ts()}] pas de parole detectee (VAD : {ratio:.0%} de "
                      f"trames parlees), ignore.")
                if self.ui:
                    self.ui.show_message("Pas de parole detectee", autohide=5.0)
                return
        except Exception:
            if peak < SPEECH_DYNAMICS_RATIO * floor:
                print(f"[{ts()}] pas de parole detectee (signal plat : crete {peak:.4f} "
                      f"< {SPEECH_DYNAMICS_RATIO} x plancher {floor:.4f}), ignore.")
                if self.ui:
                    self.ui.show_message("Pas de parole detectee", autohide=5.0)
                return
        language = self.cfg.language or self._detected_lang
        if language is None:
            # detection via le petit modele (~0,2 s) : laisser turbo detecter
            # doublait la latence de chaque dictee (+2,3 s mesures)
            language = detect_language(audio)
        self._detected_lang = None
        t0 = time.monotonic()
        try:
            text = clean(transcribe(audio, self.cfg.model, language))
        except Exception as exc:
            print(f"[erreur] transcription : {exc}")
            if self.ui:
                self.ui.show_message(f"Erreur de transcription : {exc}", autohide=6.0)
            return
        elapsed = time.monotonic() - t0
        if not text:
            print(f"[{ts()}] transcription vide, rien a coller")
            if self.ui:
                self.ui.hide_panel()
            return
        print(f"[{ts()}] transcrit en {elapsed:.1f}s : {text}")
        if self.habits:
            self.habits.record(text, target[1], language)
        if self.settings.preview_before_paste and self.ui:
            self._last = {"text": text, "target": target, "pasted": False}
            self.ui.show_final(text, pasted=False)
            return
        current = frontmost_app()
        if current[0] != target[0]:
            clipboard_set(text)
            print(f"[{ts()}] app active changee pendant la transcription "
                  f"({target[1]} -> {current[1]}) : texte laisse dans le "
                  "presse-papiers, coller avec Cmd+V.")
            self._last = {"text": text, "target": target, "pasted": False}
            if self.ui:
                self.ui.show_final(text, pasted=False,
                                   note="App changee — texte copie, coller avec Cmd+V")
            return
        self._paste(text)
        print(f"[{ts()}] colle dans {target[1]}")
        self._last = {"text": text, "target": target, "pasted": True}
        if self.ui:
            self.ui.show_final(text, pasted=True)

    # -------------------------------------------------------------- actions IA

    def request_action(self, task: str, lang: str | None = None) -> None:
        """Appele par l'UI (boutons du panneau). Traite dans le worker."""
        self._ensure_worker()
        self._jobs.put(("action", (task, lang)))

    def request_paste_last(self) -> None:
        """Bouton Coller (mode apercu avant collage, ou app changee)."""
        self._ensure_worker()
        self._jobs.put(("action", ("paste", None)))

    def _run_action(self, task: str, lang: str | None) -> None:
        if self._last is None:
            return
        src = dict(self._last)
        if task == "paste":
            self._paste_result(src["text"], src)
            return
        if self.ai is None:
            if self.ui:
                self.ui.show_message("Moteur IA indisponible", autohide=5.0)
            return
        label = ACTION_LABELS.get(task, task)
        if task == "translate":
            label += f" ({TRANSLATE_LANGS.get(lang, lang)})"
        if self.ui:
            self.ui.show_working(f"{label}…")
        context = ""
        if task in ("pro", "friendly") and self.settings.read_context:
            try:
                context = read_conversation(src["target"][0])
            except Exception:
                context = ""  # meilleur effort : le ton marche aussi sans contexte
        profile = ""
        if self.habits and self.settings.habits_enabled:
            profile = self.habits.profile_summary()
        t0 = time.monotonic()
        try:
            result = self.ai.transform(task, src["text"], lang=lang,
                                       context=context, profile=profile)
        except Exception as exc:
            print(f"[erreur] {label} : {exc}")
            if self.ui:
                self.ui.show_message(f"{label} impossible : {exc}", autohide=6.0)
            return
        print(f"[{ts()}] {label} en {time.monotonic() - t0:.1f}s : {result}")
        self._paste_result(result, src)

    def _paste_result(self, text: str, src: dict) -> None:
        """Colle un resultat a la place de la dictee d'origine si possible :
        meme app active + deja colle -> Cmd+Z puis re-collage ; meme app non
        colle -> collage simple ; app differente -> presse-papiers seulement."""
        current = frontmost_app()
        if current[0] != src["target"][0]:
            clipboard_set(text)
            self._last = {"text": text, "target": src["target"], "pasted": False}
            if self.ui:
                self.ui.show_final(text, pasted=False,
                                   note="Texte copie — coller avec Cmd+V")
            return
        self._pasting.set()
        try:
            if src["pasted"]:
                press_undo(self.kb)
            paste(text, self.kb)
        finally:
            self._pasting.clear()
        print(f"[{ts()}] colle dans {src['target'][1]}")
        self._last = {"text": text, "target": src["target"], "pasted": True}
        if self.ui:
            self.ui.show_final(text, pasted=True)

    # -------------------------------------------------------------------- boot

    def _startup_report(self) -> None:
        if load_dictionary():
            print(f"Dictionnaire personnel charge : {DICTIONARY_PATH}")
        volume = input_volume()
        if volume is not None and volume < 40:
            print(f"[attention] volume d'entree micro bas ({volume}/100) : le signal "
                  "est normalise automatiquement, mais monter l'entree ameliore la "
                  "precision (Reglages Systeme > Son > Entree).")

    def _boot_models(self) -> None:
        """Prechargements longs, en arriere-plan pour ne pas bloquer l'UI."""
        if self.ui:
            self.ui.set_status("Chargement du modele…")
        preload(self.cfg.model, self.cfg.language)
        if self.ui and self.settings.live_preview:
            preload(PREVIEW_MODEL, self.cfg.language)
        self.recorder.prepare()  # premiere ouverture du stream micro : ~2 s, payee ici
        self._startup_report()
        print(f"Pret. Maintenir [{self.cfg.key_name}] pour dicter, relacher pour "
              "coller. Ctrl+C pour quitter.")
        if self.ui:
            self.ui.set_status(f"Pret — maintenir {self.cfg.key_name} pour dicter")
            if self.ai is not None:
                self.ai.warm_up()

    def run(self) -> None:
        fn_listener = None
        if self.cfg.key_name == "fn":
            fn_listener = FnListener(self.start_recording, self.stop_recording,
                                     self.cancel_recording,
                                     is_pasting=self._pasting.is_set)
            fn_listener.prepare()
        preload_sounds("Tink", "Pop", "Bottle")
        if self.ui is not None:
            self._run_with_ui(fn_listener)
        else:
            self._run_terminal(fn_listener)

    def _run_terminal(self, fn_listener: FnListener | None) -> None:
        print("Prechargement du modele (telechargement HuggingFace au premier lancement)...")
        self._boot_models()
        if fn_listener is not None:
            fn_listener.run()
        else:
            with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
                listener.join()

    def _run_with_ui(self, fn_listener: FnListener | None) -> None:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        from PyObjCTools import AppHelper

        ns_app = NSApplication.sharedApplication()
        ns_app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        self.ui.setup()
        print("Prechargement du modele (telechargement HuggingFace au premier lancement)...")
        threading.Thread(target=self._boot_models, daemon=True).start()
        if fn_listener is not None:
            fn_listener.attach_to_current_runloop()
        else:
            keyboard.Listener(on_press=self.on_press, on_release=self.on_release).start()
        AppHelper.runEventLoop()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="localflow",
        description="Dictee vocale 100 % locale : maintenir une touche, parler, relacher.",
    )
    parser.add_argument("--model", default="turbo",
                        help="turbo (defaut), small, base, ou un repo HuggingFace mlx complet")
    parser.add_argument("--key", default="fn", choices=sorted(KEYS),
                        help="touche push-to-talk (defaut : fn, comme Wispr Flow)")
    parser.add_argument("--language", default=None,
                        help="forcer la langue (fr, en...) ; defaut : auto-detection")
    parser.add_argument("--no-ui", action="store_true",
                        help="mode terminal : pas de panneau flottant ni de barre de menus")
    args = parser.parse_args()
    cfg = Config(model=args.model, key_name=args.key, language=args.language,
                 use_ui=not args.no_ui)
    settings = Settings.load()
    if cfg.use_ui:
        from localflow.ai import AIEngine
        from localflow.habits import Habits
        from localflow.ui import UI

        app = App(cfg, settings=settings, ai=AIEngine(), habits=Habits(settings))
        app.ui = UI(settings, app)
    else:
        app = App(cfg, settings=settings)
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nArret.")
    except PermissionError as exc:
        raise SystemExit(f"Erreur : {exc}")


if __name__ == "__main__":
    main()
