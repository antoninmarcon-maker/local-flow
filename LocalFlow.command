#!/bin/zsh
# Lancement rapide de local-flow : double-clic, Spotlight ("LocalFlow"), ou Dock.
# S'ouvre dans une fenetre Terminal : les permissions macOS utilisees sont celles
# du Terminal, accordees une seule fois.
cd "$(dirname "$0")"
exec .venv/bin/localflow "$@"
