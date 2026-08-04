"""Nettoyage leger du texte transcrit."""

import re

FILLERS = re.compile(r"\b(?:euh+|heu+|hum+|um+|uh+)\b[,.]?\s*", re.IGNORECASE)


def clean(text: str) -> str:
    text = FILLERS.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
