"""Transcription locale mlx-whisper (GPU Metal).

Deux modeles cohabitent : "turbo" pour la passe finale (qualite) et "base" pour
l'apercu en direct et la detection de langue (rapidite). mlx_whisper.ModelHolder
ne cachant qu'UN modele (alterner rechargerait turbo du disque a chaque dictee),
un cache multi-modeles est installe a l'import.
"""

import logging
import threading

import numpy as np

from localflow.config import DICTIONARY_PATH, ensure_private_directory

logger = logging.getLogger("localflow")

MODELS = {
    "turbo": "mlx-community/whisper-large-v3-turbo",
    "small": "mlx-community/whisper-small-mlx",
    "base": "mlx-community/whisper-base-mlx",
}

PREVIEW_MODEL = "base"

# Toutes les inferences Whisper sont serialisees : deux transcriptions
# concurrentes (apercu + finale, ou deux dictees rapprochees) se ralentissent
# mutuellement sur GPU et l'eval mlx multi-thread n'est pas un chemin garanti.
_INFER_LOCK = threading.Lock()

_cache_installed = False


def _transcribe_module():
    """Le module mlx_whisper.transcribe -- pas la fonction du meme nom que le
    package re-exporte par-dessus (from mlx_whisper import transcribe renvoie
    la fonction, silencieusement)."""
    import importlib

    return importlib.import_module("mlx_whisper.transcribe")


_INSTALL_LOCK = threading.Lock()


def _install_multimodel_cache() -> None:
    """Remplace mlx_whisper.transcribe.ModelHolder (cache a 1 entree) par un
    cache dict {(chemin, dtype): modele}. RAM : turbo ~1,6 GB + base ~80 MB.
    Sous verrou : l'import de mlx_whisper prend ~2 s, deux threads (boot +
    apercu) pouvaient installer deux holders et charger turbo deux fois."""
    global _cache_installed
    with _INSTALL_LOCK:
        if _cache_installed:
            return
        _t = _transcribe_module()

        models: dict = {}

        class _MultiModelHolder:
            @staticmethod
            def get_model(model_path: str, dtype):
                key = (model_path, str(dtype))
                if key not in models:
                    models[key] = _t.load_model(model_path, dtype=dtype)
                return models[key]

        _t.ModelHolder = _MultiModelHolder
        _cache_installed = True


def resolve(model: str) -> str:
    return MODELS.get(model, model)


def load_dictionary() -> str | None:
    """Dictionnaire personnel : un mot/nom propre par ligne, injecte en
    initial_prompt pour biaiser Whisper (equivalent local du dictionnaire Wispr)."""
    try:
        if DICTIONARY_PATH.exists():
            ensure_private_directory(DICTIONARY_PATH.parent)
            DICTIONARY_PATH.chmod(0o600)
        lines = DICTIONARY_PATH.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    words = [w.strip() for w in lines if w.strip() and not w.startswith("#")]
    return ("Vocabulaire : " + ", ".join(words) + ".") if words else None


def looks_hallucinated(result: dict) -> bool:
    """Vrai si Whisper a probablement invente du texte sur du non-parole.

    Le bruit ambiant normalise passe parfois la garde de dynamique et Whisper
    hallucine alors une phrase plausible. Signature : tous les segments ont un
    no_speech_prob eleve, ou une avg_logprob tres basse (decodage force)."""
    segments = result.get("segments") or []
    if not segments:
        return False
    def suspicious(seg: dict) -> bool:
        return seg.get("no_speech_prob", 0.0) > 0.5 or seg.get("avg_logprob", 0.0) < -1.2
    return all(suspicious(seg) for seg in segments)


def transcribe(audio: "np.ndarray | str", model: str, language: str | None) -> str:
    import mlx_whisper  # import differe : coute ~2 s au premier appel

    _install_multimodel_cache()
    with _INFER_LOCK:
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=resolve(model),
            language=language,
            initial_prompt=load_dictionary(),
        )
    text = str(result["text"]).strip()
    if text and looks_hallucinated(result):
        probs = [round(s.get("no_speech_prob", 0.0), 2) for s in result["segments"]]
        logger.info("texte juge hallucine sur du non-parole "
                    "(no_speech_prob %s), ignore", probs)
        return ""
    return text


def detect_language(audio: np.ndarray, model: str = PREVIEW_MODEL) -> str:
    """Detecte la langue avec le petit modele (~0,1-0,3 s) au lieu de laisser
    turbo le faire (passe encodeur complete, +2,3 s mesures par dictee)."""
    import mlx.core as mx
    from mlx_whisper.audio import N_FRAMES, N_SAMPLES, log_mel_spectrogram, pad_or_trim

    _install_multimodel_cache()
    _t = _transcribe_module()
    with _INFER_LOCK:
        m = _t.ModelHolder.get_model(resolve(model), mx.float16)
        if not m.is_multilingual:
            return "en"
        mel = log_mel_spectrogram(audio, n_mels=m.dims.n_mels, padding=N_SAMPLES)
        segment = pad_or_trim(mel, N_FRAMES, axis=-2).astype(mx.float16)
        _, probs = m.detect_language(segment)
    return max(probs, key=probs.get)


def preload(model: str, language: str | None = None) -> None:
    """Charge le modele et fait une inference a vide (le premier appel reel
    paie sinon la compilation des noyaux Metal)."""
    from localflow.audio import SAMPLE_RATE

    transcribe(np.zeros(SAMPLE_RATE // 2, dtype=np.float32), model, language)
