"""Transcription locale mlx-whisper (GPU Metal).

Deux modeles cohabitent : "turbo" pour la passe finale (qualite) et "base" pour
l'apercu en direct et la detection de langue (rapidite). mlx_whisper.ModelHolder
ne cachant qu'UN modele (alterner rechargerait turbo du disque a chaque dictee),
un cache multi-modeles est installe a l'import.
"""

import threading

import numpy as np

from localflow.config import DICTIONARY_PATH

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


def _install_multimodel_cache() -> None:
    """Remplace mlx_whisper.transcribe.ModelHolder (cache a 1 entree) par un
    cache dict {(chemin, dtype): modele}. RAM : turbo ~1,6 GB + base ~80 MB."""
    global _cache_installed
    if _cache_installed:
        return
    from mlx_whisper import transcribe as _t

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
        lines = DICTIONARY_PATH.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    words = [w.strip() for w in lines if w.strip() and not w.startswith("#")]
    return ("Vocabulaire : " + ", ".join(words) + ".") if words else None


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
    return str(result["text"]).strip()


def detect_language(audio: np.ndarray, model: str = PREVIEW_MODEL) -> str:
    """Detecte la langue avec le petit modele (~0,1-0,3 s) au lieu de laisser
    turbo le faire (passe encodeur complete, +2,3 s mesures par dictee)."""
    import mlx.core as mx
    from mlx_whisper import transcribe as _t
    from mlx_whisper.audio import N_FRAMES, N_SAMPLES, log_mel_spectrogram, pad_or_trim

    _install_multimodel_cache()
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
