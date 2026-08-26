"""Contexte de l'app active : registre de ton (pro / amical) et lecture du fil
de conversation visible via l'API Accessibilite.

Tout reste on-device : le texte lu ne sert qu'a donner le ton au moteur IA
local, il n'est ni stocke ni envoye nulle part.
"""

from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementSetAttributeValue,
    AXUIElementSetMessagingTimeout,
    kAXChildrenAttribute,
    kAXFocusedWindowAttribute,
    kAXRoleAttribute,
    kAXTitleAttribute,
    kAXValueAttribute,
)

AX_TIMEOUT_S = 1.0  # sans lui, une app cible gelee bloque chaque appel ~6 s

# Apps de messagerie perso -> amical ; clients mail / outils pro -> pro.
FRIENDLY_APPS = {"whatsapp", "instagram", "messages", "telegram", "signal",
                 "discord", "messenger", "snapchat"}
PRO_APPS = {"mail", "outlook", "spark", "airmail", "thunderbird", "notion",
            "linkedin", "slack", "teams", "microsoft teams"}
# Dans un navigateur, l'app ne dit rien : on regarde le titre de la fenetre.
BROWSERS = {"safari", "google chrome", "chrome", "arc", "firefox", "brave browser",
            "microsoft edge", "opera"}
FRIENDLY_TITLE_HINTS = {"whatsapp", "instagram", "messenger", "telegram", "discord"}
PRO_TITLE_HINTS = {"gmail", "outlook", "linkedin", "mail", "proton"}

TEXT_ROLES = {"AXStaticText", "AXTextArea"}
MAX_NODES = 2500          # borne le parcours : les arbres AX de web apps sont enormes
MAX_CONTEXT_CHARS = 1500  # le modele Apple a une fenetre modeste, et la fin
                          # du fil (messages recents) est ce qui compte


def _attr(el, name):
    err, val = AXUIElementCopyAttributeValue(el, name, None)
    return val if err == 0 else None


def window_title(pid: int) -> str:
    ax_app = AXUIElementCreateApplication(pid)
    AXUIElementSetMessagingTimeout(ax_app, AX_TIMEOUT_S)
    window = _attr(ax_app, kAXFocusedWindowAttribute)
    if window is None:
        return ""
    return _attr(window, kAXTitleAttribute) or ""


def detect_register(app_name: str, title: str = "") -> str | None:
    """"pro", "amical" ou None (inconnu) selon l'app active et, pour un
    navigateur, le titre de la fenetre."""
    name = app_name.lower()
    if name in FRIENDLY_APPS:
        return "friendly"
    if name in PRO_APPS:
        return "pro"
    if name in BROWSERS and title:
        t = title.lower()
        if any(h in t for h in FRIENDLY_TITLE_HINTS):
            return "friendly"
        if any(h in t for h in PRO_TITLE_HINTS):
            return "pro"
    return None


def read_conversation(pid: int, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Texte visible de la fenetre focalisee (fil de discussion), meilleur effort.

    Chrome et les apps Electron n'exposent leur contenu web qu'apres activation
    de AXEnhancedUserInterface : on le pose puis on lit. Les apps natives
    (Messages, Mail) exposent directement. Echec ou arbre vide -> chaine vide,
    l'appelant fait sans contexte."""
    ax_app = AXUIElementCreateApplication(pid)
    AXUIElementSetMessagingTimeout(ax_app, AX_TIMEOUT_S)
    AXUIElementSetAttributeValue(ax_app, "AXEnhancedUserInterface", True)
    window = _attr(ax_app, kAXFocusedWindowAttribute)
    if window is None:
        return ""
    texts: list[str] = []
    stack, seen = [window], 0
    while stack and seen < MAX_NODES:
        el = stack.pop()
        seen += 1
        role = _attr(el, kAXRoleAttribute)
        if role in TEXT_ROLES:
            v = _attr(el, kAXValueAttribute)
            if isinstance(v, str):
                v = v.strip()
                if v and len(v) > 1:
                    texts.append(v)
        children = _attr(el, kAXChildrenAttribute)
        if children:
            stack.extend(children)
    if not texts:
        return ""
    # deduplique en gardant l'ordre (les web apps repetent les memes chaines)
    unique = list(dict.fromkeys(texts))
    joined = "\n".join(unique)
    return joined[-max_chars:]
