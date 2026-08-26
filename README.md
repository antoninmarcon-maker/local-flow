# local-flow

Dictee vocale systeme entiere, 100 % locale et privee. Equivalent local de Wispr Flow :
maintenir une touche, parler, relacher, le texte apparait dans l'application active.
Aucune donnee ne quitte la machine.

## Fonctionnement

1. Maintenir la touche push-to-talk (fn par defaut, comme Wispr Flow) : le micro
   enregistre (son "Tink"). Un panneau flottant discret s'affiche et montre la
   transcription **en direct** pendant que vous parlez.
2. Relacher (son "Pop") : transcription finale par Whisper via mlx-whisper (GPU Metal),
   nettoyage leger (euh, um...), collage dans l'app active via le presse-papiers.
3. Le panneau reste visible quelques secondes avec des boutons d'action :
   **Corriger**, **→ EN / → ES** (traduction, langues cochables dans la barre de menus),
   **Pro**, **Amical**. Chaque action reecrit le texte via **Apple Intelligence
   (on-device)** et remplace le texte deja colle (Cmd+Z + re-collage). Tout reste
   sur la machine.
4. Le presse-papiers precedent est restaure automatiquement (texte uniquement,
   et seulement s'il contient encore le texte colle). Si l'app active a change
   pendant la transcription, rien n'est colle a l'aveugle : le texte reste dans
   le presse-papiers, le panneau propose un bouton Coller.
5. Annuler une dictee en cours : presser n'importe quelle autre touche (son "Bottle"),
   ou parler moins de 0,3 s. Une vraie garde anti non-parole (VAD Silero, local)
   ignore bruit ambiant et sons non vocaux.

Francais et anglais auto-detectes (toutes les langues Whisper fonctionnent) ; la
detection passe par le petit modele d'apercu (~0,2 s), pas par le gros modele.

### Barre de menus 🎙

- **Apercu en direct pendant la dictee** : transcription intermediaire dans le panneau.
- **Valider avant de coller** : la dictee s'affiche dans le panneau, rien n'est
  colle avant le clic sur Coller (ou une action).
- **Ton adapte a l'app active** : WhatsApp/Instagram/Messages → amical,
  Mail/Outlook/LinkedIn → pro (les navigateurs sont reconnus par le titre de fenetre).
- **Lire la conversation pour le ton** *(opt-in)* : les messages visibles de la fenetre active
  (via l'Accessibilite macOS) donnent le contexte au moteur IA — uniquement
  on-device, jamais stockes.
- **Apprendre mes habitudes d'ecriture** *(opt-in)* : journal local des 200 dernieres dictees
  (`~/.config/localflow/history.jsonl`) dont est derive un profil de style
  (tutoiement, emojis, longueur...) injecte dans les reformulations, et des
  suggestions de dictionnaire (noms propres recurrents).
- **Langues de traduction** : cocher/decocher EN, ES, DE, IT, PT (defaut : EN + ES).

## Installation

Prerequis : Mac Apple Silicon, [uv](https://docs.astral.sh/uv/).

```bash
cd local-flow
uv sync
```

Le moteur IA utilise Apple Intelligence (macOS 26+, active dans Reglages Systeme) via
un petit binaire Swift compile automatiquement au premier lancement (Command Line
Tools requis : `xcode-select --install`). Si Apple Intelligence est indisponible,
repli possible sur un petit modele local mlx : `uv sync --extra fallback`.

## Lancement

```bash
uv run localflow
```

| Option | Valeurs | Defaut |
|---|---|---|
| `--model` | `turbo`, `small`, `base`, ou un repo HuggingFace mlx | `turbo` (whisper-large-v3-turbo) |
| `--key` | `fn`, `alt_r`, `cmd_r`, `ctrl_r`, `f8`, `f13` | `fn` |
| `--language` | `fr`, `en`, ... | auto-detection |
| `--no-ui` | | mode terminal : pas de panneau ni de barre de menus |

Premier lancement : telechargement des modeles depuis HuggingFace (~1,6 GB pour turbo,
~80 MB pour le modele d'apercu). Ensuite tout fonctionne hors ligne.

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
permissions deja accordees au Terminal. Quitter (et liberer la memoire) : Ctrl+C, fermer
la fenetre, ou "Quitter LocalFlow" dans le menu 🎙. Le modele reste charge tant que
l'app tourne (~2,4 GB), ce mode a la demande est le bon choix quand la RAM est juste.

Spotlight ne met pas en avant les fichiers `.command` : pour lancer depuis Spotlight ou le
Dock, creer une vraie app lanceur (une fois) :

```bash
osacompile -o ~/Applications/LocalFlow.app -e 'tell application "Terminal"
	activate
	do script "/Users/antoninmarcon/Documents/local-flow/LocalFlow.command"
end tell'
```

Ensuite Spotlight > "LocalFlow" ouvre le Terminal et lance la dictee. Au premier lancement,
macOS demande a LocalFlow.app le droit de controler le Terminal (Automation) : accepter.

### Demarrage automatique au login

```bash
./scripts/install-launchagent.sh              # installe + demarre
./scripts/install-launchagent.sh --uninstall  # desinstalle
```

Installe un LaunchAgent launchd : local-flow tourne en arriere-plan des le login.
Logs techniques sans contenu dicte dans `~/Library/Logs/LocalFlow/localflow.log` (rotation
automatique : 1 MB, deux archives). Lance hors Terminal, le process a besoin
de ses propres permissions (Surveillance de l'entree + Accessibilite pour le binaire
Python affiche par le script), puis :

```bash
launchctl kickstart -k gui/$(id -u)/com.antonin.localflow
```

## Permissions macOS (une seule fois)

Reglages Systeme > Confidentialite et securite :

1. **Microphone** : demande automatiquement au premier enregistrement, accorder a votre terminal.
2. **Surveillance de l'entree** (Input Monitoring) : ajouter votre terminal.
   Necessaire pour detecter la touche maintenue partout dans le systeme.
3. **Accessibilite** : ajouter votre terminal. Necessaire pour le Cmd+V simule
   (et, si activee, la lecture du fil de conversation pour le ton).

Relancer le terminal apres avoir accorde les permissions.

## Dictionnaire personnel

`~/.config/localflow/dictionary.txt` : un mot, nom propre ou terme de jargon par ligne
(lignes `#` ignorees). Injecte comme prompt initial de Whisper pour ameliorer leur
reconnaissance. Avec les habitudes d'ecriture activees, les noms propres recurrents
de vos dictees sont proposes dans `~/.config/localflow/suggestions-dictionnaire.txt`.

## Verification

```bash
uv run python tests/test_process.py      # chemins de traitement (doublures, sans permissions)
uv run python tests/test_fn_listener.py  # machine a etats fn (CGEvents synthetiques)
uv run python tests/test_stt.py          # gardes anti-hallucination + VAD Silero (say requis)
uv run python tests/test_context.py      # registre pro/amical par app
uv run python tests/test_settings.py     # reglages persistants
uv run python tests/test_habits.py       # habitudes d'ecriture
uv run python tests/test_logging.py      # logs prives et rotation
uv run python tests/test_security.py     # migration des permissions locales
uv run python tests/test_packaging.py    # contenu wheel/sdist
uv run python tests/test_ai.py           # moteur IA (saute si indisponible)
uv run python tests/test_ui_live.py      # vraie UI AppKit pilotee par programme (~2 s a l'ecran)
uv run python tests/test_pipeline.py     # parole synthetique FR/EN/ES + mp3 -> transcription (ffmpeg requis)
uv run ruff check localflow tests        # qualite statique
```

## Depannage : "le texte ne se colle pas"

Le terminal (ou `~/Library/Logs/LocalFlow/localflow.log`) dit toujours pourquoi :

| Message | Cause | Remede |
|---|---|---|
| rien du tout (pas de "transcription en cours...") | la touche n'est pas detectee | permission Surveillance de l'entree du terminal, relancer |
| `micro muet (crete RMS ...)` | le micro ne capte rien du tout | verifier l'entree selectionnee et son volume (Reglages Systeme > Son > Entree) |
| `pas de parole detectee (VAD ...)` | du son mais pas de voix humaine | parler plus pres du micro ; la detection (VAD Silero) est independante du volume d'entree |
| `texte juge hallucine sur du non-parole` | Whisper a invente une phrase sur du bruit | rien a faire, c'est le filet de securite qui fonctionne |
| `transcription terminee en Xs` sans collage | Accessibilite manquante pour le terminal | l'ajouter dans Confidentialite et securite > Accessibilite, relancer |
| `app active changee pendant la transcription` | le focus a bouge avant la fin | bouton Coller dans le panneau, ou Cmd+V |
| transcription tres lente (10-20 s) | pression memoire (8 GB, navigateur charge...) | fermer des apps ou `--model small` |

## Limites connues

- Champs securises (mots de passe) : macOS bloque les frappes synthetiques, c'est voulu.
- Restauration du presse-papiers : texte uniquement, une image copiee juste avant est perdue.
- Le micro entend les haut-parleurs : dicter pendant qu'une video/musique joue melange
  les deux voix (propriete du monde physique, pas un bug).
- Remplacement apres action IA : Cmd+Z + re-collage, fiable dans les champs texte
  standards ; dans les apps sans annulation (terminaux...), le texte transforme est
  colle a la suite.
- Lecture du fil de conversation : meilleur effort via l'Accessibilite ; certaines
  apps web n'exposent leur contenu qu'apres activation du mode accessibilite du
  navigateur, d'autres rien du tout — le ton marche alors sans contexte.
- Sous forte pression memoire, la premiere dictee apres une pause peut prendre
  10-20 s (les modeles ont ete pagines par macOS).
- La touche fn est captee via un event tap Quartz (elle n'emet que des flagsChanged,
  invisibles pour les listeners clavier classiques).

## Pistes d'evolution

- parakeet-mlx (2x plus rapide que turbo, meilleur en francais) comme moteur STT v3
- Raccourcis clavier pour les actions du panneau (sans la souris)
- Mode toggle (appui court demarre, appui court arrete) en plus du hold
- Historique des dictees consultable (le journal existe deja en local)
