# Todo - local-flow (clone local et prive de Wispr Flow)

Date : 2026-07-03
But : dictee vocale systeme entiere, 100 % locale, sur le MacBook M2 (8 GB) d'Antonin.
Boucle cible : maintenir une touche -> parler -> relacher -> le texte apparait dans l'app active. Aucune donnee ne quitte la machine.

## Contraintes machine
- M2, 8 GB RAM -> modele Whisper turbo si la RAM tient, sinon small. A valider par test reel.
- Python 3.14 systeme trop recent pour les wheels ML -> projet pinne en 3.12 via uv.
- Pas d'Ollama installe -> pas de couche LLM de reformulation en v1 (upgrade path documente).

## Architecture (miroir local de Wispr Flow)
1. Hotkey global (pynput) : maintenir Option droite = enregistrer, relacher = transcrire + coller. Touche configurable.
2. Capture audio (sounddevice, 16 kHz mono).
3. STT local : mlx-whisper (Apple Silicon, GPU Metal). Modele par defaut a valider au bench (large-v3-turbo vs small). FR + EN auto-detect.
4. Nettoyage leger : filler words (euh, um...), espaces. Dictionnaire personnel via initial_prompt Whisper (~/.config/localflow/dictionary.txt).
5. Injection : sauvegarde presse-papiers (pbpaste) -> pbcopy transcript -> Cmd+V simule (pynput) -> restauration presse-papiers.
6. Feedback : son systeme au debut/fin d'enregistrement.

## Plan
- [x] Recherche architecture Wispr Flow (agent web) -> docs/wispr-flow-architecture.md
- [x] Scaffold projet + git init + plan
- [x] Implementation pipeline (app.py, __main__.py)
- [x] Self-check runnable : `say` genere l'audio -> transcription -> assert contenu (FR + EN OK)
- [x] Bench modele sur la machine -> turbo par defaut : 1,1 s a chaud, transcription FR parfaite ;
      small 0,4-0,9 s mais erreur ("Tesla" pour "test") -> fallback seulement
- [x] README : setup, permissions macOS (micro + input monitoring + accessibilite), usage
- [x] Commits atomiques (chore/feat/test/docs)
- [x] Lanceurs : LocalFlow.command (rapide, permissions du Terminal) +
      scripts/install-launchagent.sh (LaunchAgent login, installe et verifie : daemon
      running, log OK, ~2,3 GB residents modele charge)
- [ ] Test manuel par Antonin : accorder les 2 permissions au binaire Python
      (chemin affiche par le script) puis kickstart, et dicter en vrai
      (seul maillon non verifiable sans les permissions macOS)

## Skips deliberes (YAGNI, a ajouter si besoin)
- Barre visuelle a l'ecran (Wispr) -> son systeme suffit en v1
- Mode toggle / double-tap -> hold-to-talk seulement
- Reformulation LLM ton-par-app -> necessite Ollama, documente comme upgrade
- Menu bar app (rumps) -> daemon CLI en v1

## Limites connues a documenter
- Champs "secure input" (mots de passe) : frappes synthetiques bloquees par macOS
- Restauration presse-papiers : texte seulement (une image copiee avant dictee est perdue)
- Premier lancement : telechargement du modele depuis HuggingFace (inference ensuite 100 % offline)
