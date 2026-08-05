---
statut: en-cours
auto-resume: false
updated: 2026-08-05T01:00:00+02:00
---

# HANDOFF - local-flow

## Objectif

v2 : dictee locale AVEC panneau flottant (apercu en direct), actions IA
on-device (corriger / traduire EN-ES cochables / pro / amical via Apple
Intelligence), ton adapte a l'app active (+ lecture du fil par Accessibilite),
habitudes d'ecriture locales, et les 9 problemes de perf de l'audit corriges.

## Fait (verifie)

- Chantier sur branche feat/panneau-ia-live (worktree
  .claude/worktrees/localflow-v2-panel-ia), commits atomiques
- Refactor complet en modules (localflow/*.py), tous les correctifs de l'audit
  integres -- details : tasks/todo.md section "Chantier v2"
- 9 suites de tests VERTES sur la machine, dont : moteur IA reel (Apple
  Intelligence repond, 0,6-2,7 s par action), UI AppKit reelle pilotee par
  programme, pipeline FR/EN/ES + mp3, VAD Silero sur signaux reels
- App complete lancee en reel : boot OK, dictee f8 captee, transcription et
  collage OK (16 s sous pression memoire : modeles pagines, comportement connu)
- README, todo, lessons a jour

## Restant (ordonne)

1. Retour de la revue adversariale finale (agent en cours au moment du handoff),
   appliquer les correctifs eventuels
2. Push + PR + merge dans main (accord donne par Antonin : "tu pourras tout
   deployer") -- repo public antoninmarcon-maker/local-flow, pas de Vercel
3. TEST CLAVIER REEL par Antonin : fn maintenu -> panneau + apercu en direct ->
   collage ; boutons Corriger / -> EN / -> ES / Pro / Amical (remplacement
   Cmd+Z) ; menu 🎙 (toggles + langues) ; "Valider avant de coller"
4. (reporte) Verif post LinkedIn du 07/07 (portfolio-weekly-linkedin),
   engagement dans ~/.claude/voice/engagement-log.md

## Pieges connus

- Le micro entend les haut-parleurs : YouTube qui joue = vraie parole transcrite
  (constate en live le 05/08, d'abord pris pour une hallucination). Verifier
  pmset -g assertions avant tout diagnostic de faux positif micro.
- Silero ONNX : chaque trame de 512 doit etre prefixee de 64 echantillons de
  contexte, sinon sorties ~0 silencieuses (localflow/vad.py).
- from mlx_whisper import transcribe importe la FONCTION (re-export du package),
  pas le module : passer par importlib pour patcher ModelHolder (localflow/stt.py).
- AppHelper.stopEventLoop() termine le process : dans un test AppKit, tout
  verifier avant, exit code explicite (tests/test_ui_live.py).
- Sous pression memoire (8 GB), premiere dictee apres pause : 10-20 s, modeles
  pagines. Pas un bug, documente au README.
- Seuils audio : ne JAMAIS revenir a un seuil de niveau absolu (lecon 07-11) ;
  la garde principale est le VAD Silero, la dynamique de trames n'est que le
  repli sans onnxruntime.
- Tester du collage synthetique pendant que quelqu'un utilise le Mac : les
  evenements partent vers SON app frontale (lecon du 03/07, re-verifiee le
  05/08 : un test a colle dans le Chrome d'Antonin pendant YouTube).
- LocalFlow.command lance depuis le repo PRINCIPAL utilise le code de main :
  pour tester avant merge, lancer depuis le worktree.

## Prochain deblocant

Retour de la revue finale, puis push + PR + merge (Restant 1-2). A la reprise
("reprends") : verifier ou en est la PR, puis Restant 3.
