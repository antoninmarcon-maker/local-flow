# local-flow

Dictee vocale systeme entiere, 100 % locale et privee. Equivalent local de Wispr Flow :
maintenir une touche, parler, relacher, le texte apparait dans l'application active.
Aucune donnee ne quitte la machine.

## Fonctionnement

1. Maintenir la touche push-to-talk (fn par defaut, comme Wispr Flow) : le micro
   enregistre (son "Tink").
2. Relacher (son "Pop") : transcription locale par Whisper via mlx-whisper (GPU Metal),
   nettoyage leger (euh, um...), collage dans l'app active via le presse-papiers.
   Chaque etape s'affiche dans le terminal ("transcription en cours...", texte transcrit).
3. Le presse-papiers precedent est restaure automatiquement (texte uniquement).
   Si l'app active a change pendant la transcription (elle peut prendre plusieurs
   secondes quand la memoire est sous pression), rien n'est colle a l'aveugle :
   le texte reste dans le presse-papiers, un message l'indique, coller avec Cmd+V.
4. Annuler une dictee en cours : presser n'importe quelle autre touche (son "Bottle"),
   ou parler moins de 0,3 s.

Francais et anglais auto-detectes (toutes les langues Whisper fonctionnent).

## Installation

Prerequis : Mac Apple Silicon, [uv](https://docs.astral.sh/uv/).

```bash
cd local-flow
uv sync
```

## Lancement

```bash
uv run localflow
```

Options :

| Option | Valeurs | Defaut |
|---|---|---|
| `--model` | `turbo`, `small`, `base`, ou un repo HuggingFace mlx | `turbo` (whisper-large-v3-turbo) |
| `--key` | `fn`, `alt_r`, `cmd_r`, `ctrl_r`, `f8`, `f13` | `fn` |
| `--language` | `fr`, `en`, ... | auto-detection |

Premier lancement : telechargement du modele depuis HuggingFace (environ 1,6 GB pour turbo).
Ensuite tout fonctionne hors ligne, y compris sans reseau.

### Touche fn

Pour un usage confortable de fn en push-to-talk :

- Reglages Systeme > Clavier > "Appuyer sur la touche fn/globe pour" -> "Ne rien faire",
  sinon un appui bref ouvre les emojis ou change la langue de saisie.
- Si la dictee Apple utilise le raccourci "Appuyer deux fois sur fn", la desactiver
  (Reglages Systeme > Clavier > Dictee) pour eviter les conflits.
- Les raccourcis systeme restent utilisables : fn+fleches, fn+F1... annulent simplement
  l'enregistrement en cours au lieu de coller du texte fantome.
- Claviers externes non Apple sans touche fn : utiliser `--key alt_r`.

### Lancement rapide (recommande sur 8 GB de RAM)

Double-cliquer `LocalFlow.command`. S'ouvre dans une fenetre Terminal et reutilise les
permissions deja accordees au Terminal. Quitter (et liberer la memoire) : Ctrl+C ou fermer
la fenetre. Le modele reste charge tant que l'app tourne (~2,3 GB), ce mode a la demande
est le bon choix quand la RAM est juste.

Spotlight ne met pas en avant les fichiers `.command` : pour lancer depuis Spotlight ou le
Dock, creer une vraie app lanceur (une fois) :

```bash
osacompile -o ~/Applications/LocalFlow.app -e 'tell application "Terminal"
	activate
	do script "/Users/antoninmarcon/Documents/Projects/local-flow/LocalFlow.command"
end tell'
```

Ensuite Spotlight > "LocalFlow" ouvre le Terminal et lance la dictee. Au premier lancement,
macOS demande a LocalFlow.app le droit de controler le Terminal (Automation) : accepter.

### Demarrage automatique au login

```bash
./scripts/install-launchagent.sh              # installe + demarre
./scripts/install-launchagent.sh --uninstall  # desinstalle
```

Installe un LaunchAgent launchd : local-flow tourne en arriere-plan, sans fenetre,
des le login. Logs dans `~/Library/Logs/localflow.log`.

Attention : lance hors Terminal, le process a besoin de ses propres permissions.
Ajouter le binaire Python affiche par le script (Surveillance de l'entree +
Accessibilite), puis redemarrer l'agent :

```bash
launchctl kickstart -k gui/$(id -u)/com.antonin.localflow
```

Empreinte memoire : environ 2,3 GB residents, le modele turbo reste charge pour une
latence de dictee d'environ 1 s. Si la RAM est juste : `--model small` (moins precis)
ou preferer `LocalFlow.command` a la demande plutot que l'agent permanent.

## Permissions macOS (une seule fois)

Reglages Systeme > Confidentialite et securite :

1. **Microphone** : demande automatiquement au premier enregistrement, accorder a votre terminal.
2. **Surveillance de l'entree** (Input Monitoring) : ajouter votre terminal.
   Necessaire pour detecter la touche maintenue partout dans le systeme.
3. **Accessibilite** : ajouter votre terminal. Necessaire pour le Cmd+V simule.

Relancer le terminal apres avoir accorde les permissions.

## Dictionnaire personnel

`~/.config/localflow/dictionary.txt` : un mot, nom propre ou terme de jargon par ligne
(lignes `#` ignorees). Injecte comme prompt initial de Whisper pour ameliorer leur
reconnaissance. Equivalent local du dictionnaire Wispr Flow.

## Verification

```bash
uv run python tests/test_pipeline.py [modele]   # parole synthetique -> transcription (ffmpeg requis)
uv run python tests/test_fn_listener.py          # machine a etats fn (CGEvents synthetiques)
uv run python tests/test_process.py              # chemins silence / bruit plat / gain bas / vide / garde de focus
```

Le premier genere de la parole avec la voix systeme (`say`), la transcrit et verifie le
texte ; il a besoin de ffmpeg (`brew install ffmpeg`). L'app en usage normal, non.

## Depannage : "le texte ne se colle pas"

Le terminal dit toujours pourquoi. Apres avoir relache la touche, lire la sortie :

| Message | Cause | Remede |
|---|---|---|
| rien du tout (pas de "transcription en cours...") | la touche n'est pas detectee | permission Surveillance de l'entree du terminal, relancer |
| `micro muet (crete RMS ...)` | le micro ne capte rien du tout | verifier l'entree selectionnee et son volume (Reglages Systeme > Son > Entree) |
| `pas de parole detectee (signal plat ...)` | du bruit constant mais pas de voix | parler plus pres du micro ; la detection est independante du volume d'entree (dynamique de la parole, pas niveau absolu) |
| `transcrit en Xs : ...` sans collage | Accessibilite manquante pour le terminal | l'ajouter dans Confidentialite et securite > Accessibilite, relancer |
| `app active changee pendant la transcription` | le focus a bouge avant la fin de la transcription | le texte est dans le presse-papiers, coller avec Cmd+V |
| transcription tres lente (10-20 s) | pression memoire (8 GB, navigateur charge...) | fermer des apps ou `--model small` |

## Limites connues

- Champs securises (mots de passe) : macOS bloque les frappes synthetiques, c'est voulu.
- Restauration du presse-papiers : texte uniquement, une image copiee juste avant est perdue.
- La touche fn est captee via un event tap Quartz (elle n'emet que des flagsChanged,
  invisibles pour les listeners clavier classiques).

## Pistes d'evolution

- Reformulation LLM locale (ton adapte par app) via Ollama
- App barre de menus (rumps) au lieu du daemon terminal
- Mode toggle (appui court demarre, appui court arrete) en plus du hold
- Lancement automatique au login (launchd)
