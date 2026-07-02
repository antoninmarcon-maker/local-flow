#!/bin/zsh
# Installe (ou desinstalle avec --uninstall) le LaunchAgent qui demarre
# local-flow automatiquement au login, en arriere-plan, sans fenetre Terminal.
set -e

LABEL="com.antonin.localflow"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$PROJECT/.venv/bin/localflow"
LOG="$HOME/Library/Logs/localflow.log"

if [[ "$1" == "--uninstall" ]]; then
  launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "LaunchAgent desinstalle."
  exit 0
fi

if [[ ! -x "$BIN" ]]; then
  echo "Erreur : $BIN introuvable. Lancer d'abord : uv sync" >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$BIN</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Interactive</string>
  <key>EnvironmentVariables</key>
  <dict><key>PYTHONUNBUFFERED</key><string>1</string></dict>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF
plutil -lint -s "$PLIST"

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

PYTHON_REAL="$(readlink -f "$PROJECT/.venv/bin/python3")"
cat <<EOF
LaunchAgent installe et demarre. Logs : $LOG

IMPORTANT : lance en arriere-plan (hors Terminal), le process a besoin de SES
propres permissions. Dans Reglages Systeme > Confidentialite et securite,
ajouter ce binaire (Cmd+Shift+G dans le selecteur pour coller le chemin) :

  $PYTHON_REAL

dans : Surveillance de l'entree  ET  Accessibilite.
Le micro sera demande automatiquement a la premiere dictee.

Controles :
  tail -f $LOG                        # suivre les logs
  launchctl kickstart -k gui/$(id -u)/$LABEL   # redemarrer
  $0 --uninstall                      # desinstaller
EOF
