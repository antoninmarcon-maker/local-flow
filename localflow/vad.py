"""Detection de parole (VAD) Silero via onnxruntime.

Pourquoi un vrai VAD : la garde par dynamique de trames laissait passer le
bruit ambiant d'une piece calme (ratio mesure jusqu'a 8), qui une fois
normalise faisait halluciner Whisper avec une confiance totale
("Sous-titrage ST' 501", no_speech_prob 0.0). Un VAD energie (WebRTC) ne
distingue pas non plus du bruit amplifie (0.96 de trames "parlees" mesurees).
Silero est un petit reseau (2,3 MB, MIT, vendorise dans localflow/data/),
~10 ms de calcul CPU par seconde d'audio, 100 % local.
"""

from pathlib import Path

import numpy as np

MODEL_PATH = Path(__file__).resolve().parent / "data" / "silero_vad.onnx"
SAMPLE_RATE = 16_000
FRAME = 512                # ~32 ms, taille imposee par Silero v5 a 16 kHz
CONTEXT = 64               # Silero v5 prefixe chaque trame de 64 echantillons
                           # de contexte (entree reelle : 576) — sans eux le
                           # modele rend ~0 partout, silencieusement
SPEECH_PROB = 0.5          # prob par trame au-dela de laquelle la trame est parlee
MIN_SPEECH_RATIO = 0.10    # part minimale de trames parlees pour une dictee
MIN_SPEECH_FRAMES = 5      # ... et au moins ~160 ms de parole au total

_session = None


def _ensure_session():
    global _session
    if _session is None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        _session = ort.InferenceSession(
            str(MODEL_PATH), sess_options=opts, providers=["CPUExecutionProvider"])
    return _session


def speech_stats(audio: np.ndarray) -> tuple[float, int]:
    """(part de trames parlees, nombre de trames parlees) sur l'audio 16 kHz.

    A appeler sur l'audio NORMALISE : la parole a tres bas gain doit etre
    remontee pour etre detectable, exactement comme pour Whisper."""
    sess = _ensure_session()
    state = np.zeros((2, 1, 128), dtype=np.float32)
    context = np.zeros(CONTEXT, dtype=np.float32)
    sr = np.array(SAMPLE_RATE, dtype=np.int64)
    voiced = 0
    total = 0
    for i in range(0, len(audio) - FRAME + 1, FRAME):
        frame = np.asarray(audio[i:i + FRAME], dtype=np.float32)
        chunk = np.concatenate([context, frame]).reshape(1, -1)
        out, state = sess.run(["output", "stateN"],
                              {"input": chunk, "state": state, "sr": sr})
        context = frame[-CONTEXT:]
        total += 1
        if float(out[0, 0]) > SPEECH_PROB:
            voiced += 1
    if total == 0:
        return 0.0, 0
    return voiced / total, voiced


def has_speech(audio: np.ndarray) -> bool:
    ratio, frames = speech_stats(audio)
    return frames >= MIN_SPEECH_FRAMES and ratio >= MIN_SPEECH_RATIO
