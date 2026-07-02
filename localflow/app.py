"""local-flow : dictee vocale systeme entiere, 100 % locale.

Maintenir la touche configuree (fn par defaut, comme Wispr Flow) : le micro
enregistre. Relacher : transcription locale (mlx-whisper, GPU Metal) puis
collage du texte dans l'application active. Aucune donnee ne quitte la machine.
"""

import argparse
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import Quartz
import sounddevice as sd
from pynput import keyboard

SAMPLE_RATE = 16_000
MIN_DURATION_S = 0.3
# ponytail: garde RMS simple contre les hallucinations Whisper sur le silence
# ("Sous-titres par Amara.org") ; passer a un vrai VAD (Silero) si insuffisant.
RMS_SILENCE_THRESHOLD = 0.005
DICTIONARY_PATH = Path.home() / ".config" / "localflow" / "dictionary.txt"

MODELS = {
    "turbo": "mlx-community/whisper-large-v3-turbo",
    "small": "mlx-community/whisper-small-mlx",
    "base": "mlx-community/whisper-base-mlx",
}

KEYS = {
    "fn": None,  # geree par FnListener (event tap Quartz), pas par pynput
    "alt_r": keyboard.Key.alt_r,
    "cmd_r": keyboard.Key.cmd_r,
    "ctrl_r": keyboard.Key.ctrl_r,
    "f8": keyboard.Key.f8,
    "f13": keyboard.Key.f13,
}

FN_KEYCODE = 63  # kVK_Function

FILLERS = re.compile(r"\b(?:euh+|heu+|hum+|um+|uh+)\b[,.]?\s*", re.IGNORECASE)


@dataclass
class Config:
    model: str
    key_name: str
    language: str | None

    @property
    def pynput_key(self) -> keyboard.Key | None:
        return KEYS[self.key_name]


class FnListener:
    """Touche fn via un event tap Quartz : pynput ne la voit pas sur macOS
    (elle n'emet que des flagsChanged, keycode 63). fn servant aussi aux combos
    systeme (fn+fleches...), l'appui d'une autre touche pendant l'enregistrement
    annule la dictee au lieu de coller du texte fantome."""

    def __init__(self, on_press, on_release, on_cancel) -> None:
        self.on_press = on_press
        self.on_release = on_release
        self.on_cancel = on_cancel
        self._fn_down = False
        self._tap = None

    def _callback(self, _proxy: object, type_: int, event: object, _refcon: object) -> object:
        if type_ == Quartz.kCGEventTapDisabledByTimeout:
            Quartz.CGEventTapEnable(self._tap, True)
        elif type_ == Quartz.kCGEventFlagsChanged:
            keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            if keycode == FN_KEYCODE:
                down = bool(Quartz.CGEventGetFlags(event) & Quartz.kCGEventFlagMaskSecondaryFn)
                if down and not self._fn_down:
                    self._fn_down = True
                    self.on_press()
                elif not down and self._fn_down:
                    self._fn_down = False
                    self.on_release()
        elif type_ == Quartz.kCGEventKeyDown and self._fn_down:
            self._fn_down = False  # la release de fn qui suivra sera ignoree
            self.on_cancel()
        return event

    def prepare(self) -> None:
        """Cree le tap avant le chargement du modele : echec de permission = sortie
        immediate, sans charger 2 GB pour rien."""
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            | Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
            self._callback,
            None,
        )
        if self._tap is None:
            raise PermissionError(
                "Impossible d'ecouter le clavier. Ajouter votre terminal dans "
                "Reglages Systeme > Confidentialite et securite > Surveillance de "
                "l'entree, relancer le terminal, puis reessayer."
            )

    def run(self) -> None:
        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self._tap, True)
        Quartz.CFRunLoopRun()


class Recorder:
    """Capture micro en continu tant que la touche est maintenue."""

    def __init__(self) -> None:
        self._blocks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._blocks = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            callback=lambda indata, *_: self._blocks.append(indata.copy()),
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._blocks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._blocks)[:, 0]


def load_dictionary() -> str | None:
    """Dictionnaire personnel : un mot/nom propre par ligne, injecte en
    initial_prompt pour biaiser Whisper (equivalent local du dictionnaire Wispr)."""
    try:
        lines = DICTIONARY_PATH.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    words = [w.strip() for w in lines if w.strip() and not w.startswith("#")]
    return ("Vocabulaire : " + ", ".join(words) + ".") if words else None


def transcribe(audio: "np.ndarray | str", model: str, language: str | None) -> str:
    import mlx_whisper  # import differe : coute ~2 s au premier appel

    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=MODELS.get(model, model),
        language=language,
        initial_prompt=load_dictionary(),
    )
    return str(result["text"]).strip()


def clean(text: str) -> str:
    text = FILLERS.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clipboard_get() -> str:
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout


def clipboard_set(text: str) -> None:
    subprocess.run(["pbcopy"], input=text, text=True, check=True)


def play_sound(name: str) -> None:
    subprocess.Popen(
        ["afplay", f"/System/Library/Sounds/{name}.aiff"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def paste(text: str, kb: keyboard.Controller) -> None:
    """Colle via presse-papiers + Cmd+V simule, puis restaure le presse-papiers.
    ponytail: restauration texte seulement ; une image copiee juste avant est perdue."""
    saved = clipboard_get()
    clipboard_set(text)
    time.sleep(0.05)
    with kb.pressed(keyboard.Key.cmd):
        kb.press("v")
        kb.release("v")
    time.sleep(0.3)  # laisse l'app cible lire le presse-papiers avant restauration
    if saved:
        clipboard_set(saved)


class App:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.recorder = Recorder()
        self.kb = keyboard.Controller()
        self.recording = False

    def start_recording(self) -> None:
        if self.recording:
            return
        self.recording = True
        play_sound("Tink")
        self.recorder.start()

    def stop_recording(self) -> None:
        if not self.recording:
            return
        self.recording = False
        audio = self.recorder.stop()
        play_sound("Pop")
        if len(audio) / SAMPLE_RATE < MIN_DURATION_S:
            return
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def cancel_recording(self) -> None:
        if not self.recording:
            return
        self.recording = False
        self.recorder.stop()
        play_sound("Bottle")

    def on_press(self, key: object) -> None:
        if key == self.cfg.pynput_key:
            self.start_recording()

    def on_release(self, key: object) -> None:
        if key == self.cfg.pynput_key:
            self.stop_recording()

    def _process(self, audio: np.ndarray) -> None:
        if float(np.sqrt(np.mean(np.square(audio)))) < RMS_SILENCE_THRESHOLD:
            return
        t0 = time.monotonic()
        try:
            text = clean(transcribe(audio, self.cfg.model, self.cfg.language))
        except Exception as exc:
            print(f"[erreur] transcription : {exc}")
            return
        if not text:
            return
        paste(text, self.kb)
        elapsed = time.monotonic() - t0
        print(f"[{time.strftime('%H:%M:%S')}] {len(audio) / SAMPLE_RATE:.1f}s de parole "
              f"-> transcrit en {elapsed:.1f}s : {text}")

    def run(self) -> None:
        fn_listener = None
        if self.cfg.key_name == "fn":
            fn_listener = FnListener(self.start_recording, self.stop_recording, self.cancel_recording)
            fn_listener.prepare()
        print("Prechargement du modele (telechargement HuggingFace au premier lancement)...")
        transcribe(np.zeros(SAMPLE_RATE // 2, dtype=np.float32), self.cfg.model, self.cfg.language)
        print(f"Pret. Maintenir [{self.cfg.key_name}] pour dicter, relacher pour coller. "
              "Ctrl+C pour quitter.")
        if load_dictionary():
            print(f"Dictionnaire personnel charge : {DICTIONARY_PATH}")
        if fn_listener is not None:
            fn_listener.run()
        else:
            with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
                listener.join()


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
    args = parser.parse_args()
    cfg = Config(model=args.model, key_name=args.key, language=args.language)
    try:
        App(cfg).run()
    except KeyboardInterrupt:
        print("\nArret.")
    except PermissionError as exc:
        raise SystemExit(f"Erreur : {exc}")


if __name__ == "__main__":
    main()
