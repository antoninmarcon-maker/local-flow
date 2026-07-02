# local-flow

Dictee vocale systeme entiere, 100 % locale et privee. Equivalent local de Wispr Flow :
maintenir une touche, parler, relacher, le texte apparait dans l'application active.
Aucune donnee ne quitte la machine.

## Fonctionnement

1. Maintenir la touche push-to-talk (fn par defaut, comme Wispr Flow) : le micro
   enregistre (son "Tink").
2. Relacher (son "Pop") : transcription locale par Whisper via mlx-whisper (GPU Metal),
   nettoyage leger (euh, um...), collage dans l'app active via le presse-papiers.
3. Le presse-papiers precedent est restaure automatiquement (texte uniquement).
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

Double-cliquer `LocalFlow.command` (ou Spotlight : taper "LocalFlow", ou l'epingler au Dock).
S'ouvre dans une fenetre Terminal et reutilise les permissions deja accordees au Terminal.
Quitter (et liberer la memoire) : Ctrl+C ou fermer la fenetre. Le modele restant charge
tant que l'app tourne (~2,3 GB), ce mode a la demande est le bon choix quand la RAM est juste.

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
uv run python tests/test_pipeline.py [modele]
```

Genere de la parole avec la voix systeme (`say`), la transcrit et verifie le texte.
Le test a besoin de ffmpeg (`brew install ffmpeg`) ; l'app en usage normal, non.

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
