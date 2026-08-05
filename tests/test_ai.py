"""Self-check du moteur IA (Apple Intelligence via afmshim, ou repli mlx-lm).

Saute proprement si aucun backend n'est disponible sur la machine (le moteur
n'est pas requis pour la dictee de base). Les assertions sont volontairement
laches : un LLM ne rend pas deux fois le meme texte, on verifie le contrat
(langue cible, correction des graphies phonetiques, registre).

Usage : uv run python tests/test_ai.py
"""

from localflow.ai import AIEngine


def main() -> None:
    engine = AIEngine()
    engine.warm_up()
    if engine.backend == "off":
        print("SKIP : aucun moteur IA disponible sur cette machine")
        return

    corrected = engine.transform(
        "correct", "alors euh la reunion elle est décalé a demain passque le client est pas la")
    print(f"  correct : {corrected!r}")
    low = corrected.lower()
    assert "euh" not in low, corrected
    assert "passque" not in low and "parce" in low, corrected
    assert "réunion" in low or "reunion" in low, corrected

    en = engine.transform("translate", "La réunion de demain est décalée à quinze heures.", lang="en")
    print(f"  en      : {en!r}")
    assert "meeting" in en.lower(), en
    assert "tomorrow" in en.lower(), en

    es = engine.transform("translate", "La réunion de demain est décalée à quinze heures.", lang="es")
    print(f"  es      : {es!r}")
    assert "reunión" in es.lower() or "reunion" in es.lower(), es
    assert "mañana" in es.lower() or "manana" in es.lower(), es

    pro = engine.transform("pro", "salut ca marche pas ton truc tu peux regarder")
    print(f"  pro     : {pro!r}")
    assert "salut" not in pro.lower(), pro
    assert "vous" in pro.lower() or "pourriez" in pro.lower(), pro

    friendly = engine.transform(
        "friendly", "Je vous informe que je serai en retard de quinze minutes.",
        profile="tutoie spontanement, messages courts")
    print(f"  friendly: {friendly!r}")
    assert "je vous informe" not in friendly.lower(), friendly
    assert "15" in friendly or "quinze" in friendly.lower(), friendly

    print(f"OK : moteur IA ({engine.backend}) — correction, EN, ES, pro, amical")


if __name__ == "__main__":
    main()
