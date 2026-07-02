# local-flow

Dictee vocale systeme entiere, 100 % locale et privee. Equivalent local de Wispr Flow :
maintenir une touche, parler, relacher, le texte apparait dans l'application active.
Aucune donnee ne quitte la machine.

## Fonctionnement

1. Maintenir la touche push-to-talk (Option droite par defaut) : le micro enregistre (son "Tink").
2. Relacher (son "Pop") : transcription locale par Whisper via mlx-whisper (GPU Metal),
   nettoyage leger (euh, um...), collage dans l'app active via le presse-papiers.
3. Le presse-papiers precedent est restaure automatiquement (texte uniquement).

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
| `--key` | `alt_r`, `cmd_r`, `ctrl_r`, `f8`, `f13` | `alt_r` (Option droite) |
| `--language` | `fr`, `en`, ... | auto-detection |

Premier lancement : telechargement du modele depuis HuggingFace (environ 1,6 GB pour turbo).
Ensuite tout fonctionne hors ligne, y compris sans reseau.

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
- La touche fn (celle de Wispr Flow) n'est pas capturable simplement en userspace,
  d'ou Option droite par defaut.

## Pistes d'evolution

- Reformulation LLM locale (ton adapte par app) via Ollama
- App barre de menus (rumps) au lieu du daemon terminal
- Mode toggle (appui court demarre, appui court arrete) en plus du hold
- Lancement automatique au login (launchd)
