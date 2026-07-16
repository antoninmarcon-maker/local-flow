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
- [x] Choix d'usage (Antonin, 2026-07-03) : lancement A LA DEMANDE via LocalFlow.command,
      RAM souvent juste -> LaunchAgent desinstalle (le script reste dispo dans le repo)
- [x] Touche fn par defaut (demande Antonin) : event tap Quartz (flagsChanged keycode 63),
      annulation si autre touche pressee pendant l'enregistrement (combos fn+fleches),
      fail-fast permission avant chargement du modele ; machine a etats testee par
      CGEvents synthetiques, boot reel verifie
- [x] Debug "le texte ne se colle pas" (2026-07-03) : permissions TCC toutes OK
      (verifie par sondes dans Terminal), collage CGEventPost sain meme apres mlx
      (event tap observateur 10/10). Causes reelles : transcription 1,3-14,5 s selon
      pression memoire pendant laquelle le focus change, chemins de sortie muets,
      volume d'entree micro 27/100. Fix : garde de focus + message sur chaque chemin
      + alerte volume. Self-checks verts + boucle re-verifiee en live (F8 + say).
- [x] Repo GitHub public cree et pousse (antoninmarcon-maker/local-flow)
- [x] Test manuel par Antonin (2026-07-03) : VALIDE, la boucle fn -> parole ->
      collage fonctionne au clavier reel. Projet operationnel.
- [x] Fix garde anti-silence (2026-07-11) : le seuil RMS absolu (0.005) avalait la
      dictee a volume d'entree bas (38/100 -> RMS clip 0.0002-0.0019, 3 dictees
      consecutives ignorees). Remplace par une detection par dynamique de trames
      (crete p95 >= 3 x plancher p10 des RMS de 30 ms, invariante au gain : parole
      reelle mesuree >= 7, bruit plat <= 1.8) + normalisation du signal avant
      Whisper. Verifie E2E au vrai modele aux 3 niveaux RMS du bug : transcription
      identique aux 3 gains. Test de regression : echoue sur l'ancien code,
      passe sur le nouveau. TEST CLAVIER REEL VALIDE par Antonin (2026-07-12),
      volume micro laisse a 38/100 : la dictee colle. Merge dans main.

## Skips deliberes (YAGNI, a ajouter si besoin)
- Barre visuelle a l'ecran (Wispr) -> son systeme suffit en v1
- Mode toggle / double-tap -> hold-to-talk seulement
- Reformulation LLM ton-par-app -> necessite Ollama, documente comme upgrade
- Menu bar app (rumps) -> daemon CLI en v1

## Limites connues a documenter
- Champs "secure input" (mots de passe) : frappes synthetiques bloquees par macOS
- Restauration presse-papiers : texte seulement (une image copiee avant dictee est perdue)
- Premier lancement : telechargement du modele depuis HuggingFace (inference ensuite 100 % offline)
