"""Moteur IA local : corriger / traduire / reformuler (pro, amical).

Backend principal : Apple Intelligence via un petit binaire Swift
(native/afmshim.swift), compile automatiquement au premier lancement.
On-device, zero RAM residente pour local-flow (modele systeme gere par macOS).

Repli si Apple Intelligence est indisponible (desactive, ancien macOS...) :
mlx-lm avec un petit modele 4-bit, si le groupe optionnel est installe
(uv sync --extra fallback). Dans les deux cas, rien ne quitte la machine.
"""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from localflow.config import SHIM_DIR

SHIM_SOURCE = Path(__file__).resolve().parent.parent / "native" / "afmshim.swift"
MAX_TEXT_CHARS = 4000     # fenetre modeste du modele Apple (~4k tokens)
MAX_CONTEXT_CHARS = 1500
MAX_PROFILE_CHARS = 300
TRANSFORM_TIMEOUT_S = 90  # premier appel : macOS peut devoir charger son modele

FALLBACK_MODEL = "mlx-community/Qwen3-1.7B-4bit"

FALLBACK_PROMPTS = {
    "correct": "Corrige l'orthographe, la grammaire et la ponctuation de ce texte "
               "dicte (tics oraux et graphies phonetiques inclus), sans changer le "
               "sens, le ton ni la langue. Reponds uniquement avec le texte corrige.",
    "translate": "Traduis ce texte en {lang_name}, en conservant ton et registre. "
                 "Reponds uniquement avec la traduction.",
    "pro": "Reecris ce texte dans un registre professionnel courtois, en conservant "
           "toutes les informations, sans rien inventer, dans la meme langue. "
           "Reponds uniquement avec le texte reecrit.",
    "friendly": "Reecris ce texte dans un registre amical et naturel (message a un "
                "proche, tutoiement), en conservant toutes les informations, dans la "
                "meme langue. Reponds uniquement avec le texte reecrit.",
}

LANG_NAMES = {"en": "anglais", "es": "espagnol", "de": "allemand",
              "it": "italien", "pt": "portugais", "fr": "francais"}


class AIError(Exception):
    pass


class AIEngine:
    """backend : None (pas encore sonde), "afm" (Apple Intelligence), "mlx"
    (repli mlx-lm) ou "off" (aucun disponible, message explicite a l'usage)."""

    def __init__(self) -> None:
        self.backend: str | None = None
        self._shim_bin: Path | None = None
        self._unavailable_reason = ""

    # ------------------------------------------------------------------- shim

    def _ensure_shim(self) -> Path:
        """Compile le shim si absent ou si la source a change (hash dans le nom)."""
        source = SHIM_SOURCE.read_text(encoding="utf-8")
        digest = hashlib.sha256(source.encode()).hexdigest()[:12]
        bin_path = SHIM_DIR / f"afmshim-{digest}"
        if bin_path.exists():
            return bin_path
        if shutil.which("swiftc") is None:
            raise AIError("swiftc introuvable (installer les Command Line Tools : "
                          "xcode-select --install)")
        SHIM_DIR.mkdir(parents=True, exist_ok=True)
        print("Compilation du pont Apple Intelligence (une fois, ~15 s)...")
        result = subprocess.run(
            ["swiftc", "-parse-as-library", "-O", "-o", str(bin_path), str(SHIM_SOURCE)],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise AIError(f"compilation du shim echouee : {result.stderr.strip()[:300]}")
        for old in SHIM_DIR.glob("afmshim-*"):
            if old != bin_path:
                old.unlink(missing_ok=True)
        return bin_path

    def _call_shim(self, payload: dict, timeout: float = TRANSFORM_TIMEOUT_S) -> str:
        result = subprocess.run(
            [str(self._shim_bin)], input=json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            raise AIError(f"shim termine en erreur : {result.stderr.strip()[:200]}")
        try:
            out = json.loads(result.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            raise AIError(f"reponse shim illisible : {result.stdout[:200]}")
        if not out.get("ok"):
            raise AIError(out.get("error", "erreur inconnue"))
        return str(out.get("text", "")).strip()

    # ------------------------------------------------------------------- boot

    def warm_up(self) -> None:
        """Determine le backend disponible. Appele en arriere-plan au boot."""
        try:
            self._shim_bin = self._ensure_shim()
            self._call_shim({"task": "probe"}, timeout=60)
            self.backend = "afm"
            print("Moteur IA : Apple Intelligence (on-device)")
            return
        except (AIError, subprocess.TimeoutExpired, OSError) as exc:
            self._unavailable_reason = str(exc)
        try:
            import mlx_lm  # noqa: F401  present seulement avec --extra fallback

            self.backend = "mlx"
            print(f"Moteur IA : repli mlx-lm ({FALLBACK_MODEL}) — "
                  f"Apple Intelligence indisponible ({self._unavailable_reason})")
        except ImportError:
            self.backend = "off"
            print(f"Moteur IA indisponible : {self._unavailable_reason}. "
                  "Repli possible : uv sync --extra fallback (mlx-lm).")

    # -------------------------------------------------------------- transform

    def transform(self, task: str, text: str, lang: str | None = None,
                  context: str = "", profile: str = "") -> str:
        if self.backend is None:
            self.warm_up()
        if self.backend == "off":
            raise AIError(f"aucun moteur IA ({self._unavailable_reason})")
        payload = {
            "task": task,
            "text": text[:MAX_TEXT_CHARS],
            "lang": lang or "en",
            "context": context[-MAX_CONTEXT_CHARS:],
            "profile": profile[:MAX_PROFILE_CHARS],
        }
        if self.backend == "afm":
            try:
                result = self._call_shim(payload)
                if result:
                    return result
                raise AIError("reponse vide du modele")
            except subprocess.TimeoutExpired:
                raise AIError("Apple Intelligence ne repond pas (timeout)")
        return self._mlx_transform(payload)

    def _mlx_transform(self, payload: dict) -> str:
        from mlx_lm import generate, load

        model, tokenizer = load(FALLBACK_MODEL)
        instruction = FALLBACK_PROMPTS[payload["task"]].format(
            lang_name=LANG_NAMES.get(payload["lang"], payload["lang"]))
        parts = []
        if payload["profile"]:
            parts.append(f"Habitudes d'ecriture de l'utilisateur : {payload['profile']}")
        if payload["context"] and payload["task"] in ("pro", "friendly"):
            parts.append("Derniers messages de la conversation (adapte le registre) :\n"
                         + payload["context"])
        parts.append(f"{instruction}\n\nTexte : {payload['text']}")
        messages = [{"role": "user", "content": "\n\n".join(parts)}]
        prompt = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, enable_thinking=False)
        out = generate(model, tokenizer, prompt=prompt, max_tokens=1000, verbose=False)
        return out.strip()
