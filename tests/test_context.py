"""Self-check du choix de registre selon l'app active (et le titre de fenetre
pour les navigateurs). La lecture AX reelle n'est pas testee ici (elle depend
de l'app au premier plan) ; voir tests/test_ui_live.py.

Usage : uv run python tests/test_context.py
"""

from localflow.context import detect_register


def test_apps_directes() -> None:
    assert detect_register("WhatsApp") == "friendly"
    assert detect_register("Messages") == "friendly"
    assert detect_register("Instagram") == "friendly"
    assert detect_register("Mail") == "pro"
    assert detect_register("Outlook") == "pro"
    assert detect_register("Slack") == "pro"


def test_navigateur_selon_titre() -> None:
    assert detect_register("Google Chrome", "(2) WhatsApp") == "friendly"
    assert detect_register("Safari", "Instagram • Direct") == "friendly"
    assert detect_register("Google Chrome", "Boite de reception - Gmail") == "pro"
    assert detect_register("Arc", "LinkedIn | Messagerie") == "pro"
    assert detect_register("Google Chrome", "YouTube") is None


def test_inconnu() -> None:
    assert detect_register("Notes") is None
    assert detect_register("Terminal") is None
    assert detect_register("Google Chrome", "") is None


if __name__ == "__main__":
    test_apps_directes()
    test_navigateur_selon_titre()
    test_inconnu()
    print("OK : registre par app (direct, navigateur+titre, inconnu)")
