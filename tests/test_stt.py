"""Self-check des gardes STT : detection d'hallucination sur non-parole.

Usage : uv run python tests/test_stt.py
"""

from localflow.stt import looks_hallucinated


def seg(no_speech: float, logprob: float) -> dict:
    return {"no_speech_prob": no_speech, "avg_logprob": logprob}


def test_parole_normale_gardee() -> None:
    result = {"segments": [seg(0.02, -0.3), seg(0.10, -0.4)]}
    assert not looks_hallucinated(result)


def test_non_parole_rejete() -> None:
    # bruit ambiant : Whisper doute (no_speech eleve) sur tous les segments
    assert looks_hallucinated({"segments": [seg(0.72, -0.5)]})
    # decodage force : logprob tres basse partout
    assert looks_hallucinated({"segments": [seg(0.10, -1.5), seg(0.20, -1.4)]})


def test_mixte_garde() -> None:
    # un segment franc de parole suffit a garder le texte
    result = {"segments": [seg(0.9, -1.5), seg(0.05, -0.3)]}
    assert not looks_hallucinated(result)


def test_sans_segments_garde() -> None:
    assert not looks_hallucinated({"segments": []})
    assert not looks_hallucinated({})


def test_vad_signaux_reels() -> None:
    """Le VAD Silero (vendorise, ONNX) accepte la parole -- meme a tres bas
    gain une fois normalisee -- et rejette bruit blanc et sinus, que la garde
    par dynamique de trames laissait passer une fois normalises."""
    import subprocess
    import tempfile
    import wave
    from pathlib import Path

    import numpy as np

    from localflow.audio import SAMPLE_RATE, normalize, speech_levels
    from localflow.vad import has_speech

    def norm(a: np.ndarray) -> np.ndarray:
        return normalize(a, speech_levels(a)[1])

    noise = np.random.default_rng(1).normal(size=int(1.5 * SAMPLE_RATE)).astype(np.float32) * 0.002
    assert not has_speech(norm(noise)), "bruit blanc pris pour de la parole"

    t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    env = (np.sin(2 * np.pi * 3.3 * t) > 0).astype(np.float32)
    tone = (0.1 * env * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    assert not has_speech(norm(tone)), "sinus en rafales pris pour de la parole"

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "fr.wav"
        subprocess.run(
            [
                "say",
                "-o",
                str(p),
                "--file-format=WAVE",
                "--data-format=LEI16@16000",
                "-v",
                "Thomas",
                "Bonjour, on se retrouve demain.",
            ],
            check=True,
        )
        with wave.open(str(p), "rb") as stream:
            assert stream.getframerate() == SAMPLE_RATE
            assert stream.getsampwidth() == 2
            speech = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2")
            speech = speech.astype(np.float32) / 32768.0
            if stream.getnchannels() > 1:
                speech = speech.reshape(-1, stream.getnchannels()).mean(axis=1)
        assert has_speech(speech), "parole synthetique non detectee"
        assert has_speech(norm(speech * 0.001)), "parole faible normalisee non detectee"


if __name__ == "__main__":
    test_parole_normale_gardee()
    test_non_parole_rejete()
    test_mixte_garde()
    test_sans_segments_garde()
    test_vad_signaux_reels()
    print("OK : garde anti-hallucination + VAD Silero (parole, bruit, sinus, bas gain)")
