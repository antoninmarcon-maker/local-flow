---
statut: termine
auto-resume: false
updated: 2026-07-12T00:05:00+02:00
---

# HANDOFF - local-flow

## Objectif

Dictee vocale 100 % locale (clone Wispr Flow) operationnelle sur le M2 8 GB :
maintenir fn, parler, relacher, le texte se colle dans l'app active. ATTEINT,
y compris a volume d'entree micro bas (fix garde anti-silence valide et merge).

## Fait (verifie)

- App complete sur main : pipeline mlx-whisper turbo, fn via event tap Quartz,
  annulation combo, dictionnaire personnel, collage Cmd+V + restauration
- Debug du 2026-07-03 clos (garde de focus, chemins de sortie parlants, alerte
  volume). Test manuel fn VALIDE par Antonin le 03/07. Details : tasks/todo.md
- Repo GitHub PUBLIC : https://github.com/antoninmarcon-maker/local-flow
- FIX GARDE ANTI-SILENCE (2026-07-11, branche claude/localflow-mic-sensitivity-250316,
  3 commits NON POUSSES : f93938a fix, b744084 readme, f773de7 tasks) :
  le seuil RMS absolu 0.005 rejetait la vraie parole a 38/100 de volume d'entree
  (RMS clip 0.0002-0.0019, 3 dictees avalees le 11/07 a 22h20). Remplace par une
  detection par dynamique de trames (crete p95 >= 3 x plancher p10 des RMS de
  30 ms, invariante au gain : parole reelle >= 7, bruit plat <= 1.8) +
  normalisation crete 0.9 avant Whisper. VERIFIE : test de regression qui echoue
  sur l'ancien code et passe sur le nouveau, E2E vrai modele turbo aux 3 niveaux
  RMS du bug (transcription identique aux 3 gains), suite complete verte
  (test_process 6 chemins, test_fn_listener, test_pipeline EN+FR)
- gstack mis a jour 1.57.9.0 -> 1.60.1.0 (2026-07-11)

## Restant (ordonne)

1. (reporte du 03/07, a verifier) Post LinkedIn local-flow : etait planifie mardi
   07/07 via portfolio-weekly-linkedin. Verifier s'il est parti ; mesure J+7
   (~14/07) dans ~/.claude/voice/engagement-log.md
2. (optionnel) Nettoyage : supprimer le worktree
   .claude/worktrees/localflow-mic-sensitivity-250316 et la branche
   claude/localflow-mic-sensitivity-250316 (mergee dans main)
3. (optionnel) Piste v2 : parakeet-mlx (2x plus rapide, meilleur en francais)
4. (optionnel) Ameliorations README listees dans Pistes d'evolution

## Prochain deblocant

Rien de bloquant : fix garde anti-silence VALIDE au clavier reel par Antonin
(2026-07-12, volume micro laisse a 38/100) et merge dans main. A la reprise
("reprends"), traiter le Restant 1 (verif post LinkedIn) ou le nettoyage du
worktree si Antonin le demande.

## Pieges connus

- Premiere inference d'un process : chargement modele ~5-10 s, attendre "Pret.".
  Sous pression memoire une transcription peut prendre 10-20 s ("transcription
  en cours..." s'affiche).
- Permissions TCC attachees au host : Terminal pour LocalFlow.command.
- Restauration presse-papiers : texte seulement.
- Tester du collage synthetique pendant que quelqu'un utilise le Mac : les
  evenements partent vers SON app frontale (lecons du 03/07).
- Seuils audio : ne JAMAIS revenir a un seuil de niveau absolu, il n'est pas
  invariant au gain d'entree micro (lecon du 11/07). La doublure parole() des
  tests doit garder une dynamique de parole (un sinus plat est rejete).
- LocalFlow.command lance depuis le repo PRINCIPAL utilise le code de main,
  pas celui de la branche worktree : pour tester le fix avant merge, lancer
  depuis le worktree ou merger d'abord.
