"""Capture micro et analyse du signal."""

import logging
import threading

import numpy as np
import sounddevice as sd

logger = logging.getLogger("localflow")

SAMPLE_RATE = 16_000
MIN_DURATION_S = 0.3
# ponytail: garde anti-silence par dynamique de trames, invariante au gain micro.
# L'ancien seuil RMS absolu (0.005) avalait la vraie parole a volume d'entree bas
# (38/100 -> RMS 0.0002-0.0019). La parole module (syllabes, pauses) : crete/plancher
# mesure >= 7 quel que soit le gain ; bruit plat <= 1.8. Vrai VAD (Silero) si insuffisant.
FRAME_S = 0.03
SILENCE_PEAK_RMS = 1e-5      # crete sous ce niveau : micro muet / zeros numeriques
# Parole reelle mesuree >= 7, bruit plat <= 1.8 ; le bruit ambiant d'une piece
# calme (clics, ventilateur) monte a ~3-4 et se faisait halluciner par Whisper
# une fois normalise (constate en live le 2026-08-05 : "that's a lot of fashion").
SPEECH_DYNAMICS_RATIO = 4.5  # crete p95 >= 4.5 x plancher p10 => parole


class Recorder:
    """Capture micro en continu tant que la touche est maintenue.

    Le stream CoreAudio est ouvert une fois (prepare) puis start/stop par dictee :
    la premiere ouverture coute ~2 s (mesure), pendant lesquelles les premieres
    syllabes n'existaient simplement pas. Ouvert mais arrete, le micro est eteint
    (pas d'indicateur orange entre les dictees)."""

    def __init__(self) -> None:
        self._blocks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._armed = False
        self._lock = threading.Lock()
        self.overflowed = False

    def _on_block(self, indata: np.ndarray, _frames: int, _time: object, status: object) -> None:
        if not self._armed:
            return
        if status:
            self.overflowed = True
        self._blocks.append(indata.copy())

    def _open(self) -> sd.InputStream:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=self._on_block,
        )
        return stream

    def prepare(self) -> None:
        """Ouvre le stream sans le demarrer. A appeler au boot (cout paye une fois)."""
        with self._lock:
            if self._stream is None:
                self._stream = self._open()

    def start(self) -> None:
        with self._lock:
            self._blocks = []
            self.overflowed = False
            if self._stream is None:
                self._stream = self._open()
            try:
                self._stream.start()
            except Exception:  # noqa: BLE001 - backend CoreAudio tiers
                # stream invalide (peripherique debranche...) : on le recree une fois
                try:
                    self._stream.close()
                except Exception as exc:  # noqa: BLE001 - fermeture best-effort
                    logger.debug("fermeture du stream ignoree (%s)", type(exc).__name__)
                self._stream = self._open()
                self._stream.start()
            self._armed = True

    def stop(self) -> np.ndarray:
        with self._lock:
            self._armed = False
            if self._stream is not None:
                try:
                    self._stream.stop()  # draine les callbacks avant le concatenate
                except Exception as exc:  # noqa: BLE001 - arret best-effort
                    logger.debug("arret du stream ignore (%s)", type(exc).__name__)
            if not self._blocks:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._blocks)[:, 0]

    def snapshot(self) -> np.ndarray:
        """Copie de l'audio accumule, sans arreter la capture (apercu en direct).
        Le callback ne fait qu'append : une copie de la liste suffit sous GIL."""
        blocks = list(self._blocks)
        if not blocks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(blocks)[:, 0]

    def close(self) -> None:
        with self._lock:
            self._armed = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as exc:  # noqa: BLE001 - fermeture best-effort
                    logger.debug("fermeture du stream ignoree (%s)", type(exc).__name__)
                self._stream = None


def speech_levels(audio: np.ndarray) -> tuple[float, float]:
    """(plancher p10, crete p95) des RMS par trame de 30 ms. La parole se
    reconnait a sa dynamique (crete >> plancher), pas a son niveau absolu
    qui depend du gain d'entree micro."""
    n = int(SAMPLE_RATE * FRAME_S)
    usable = len(audio) - len(audio) % n
    levels = np.sqrt(np.mean(np.square(audio[:usable].reshape(-1, n)), axis=1))
    return float(np.percentile(levels, 10)), float(np.percentile(levels, 95))


def normalize(audio: np.ndarray, peak: float) -> np.ndarray:
    """Remonte un signal trop bas avant Whisper (volume d'entree micro bas).

    ponytail: jamais sur abs(audio).max() -- un seul transitoire (clac de la
    touche fn a 10 cm du micro interne) ecrasait le facteur de gain et laissait
    la parole 30x trop basse. On se cale sur la crete p95 des RMS de trame
    (robuste, deja calculee par speech_levels) et on borne le gain."""
    if peak <= 0:
        return audio
    gain = min(0.1 / peak, 100.0)
    if gain <= 1.0:
        return audio
    return np.clip(audio * gain, -1.0, 1.0)
