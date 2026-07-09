---
statut: termine
auto-resume: false
updated: 2026-07-03T13:00:00+02:00
---

# HANDOFF - local-flow

## Objectif

Dictee vocale 100 % locale (clone Wispr Flow) operationnelle sur le M2 8 GB :
maintenir fn, parler, relacher, le texte se colle dans l'app active. ATTEINT.

## Fait (verifie)

- App complete sur main : pipeline mlx-whisper turbo, fn via event tap Quartz,
  annulation combo, garde RMS, dictionnaire personnel, collage Cmd+V + restauration
- Debug du 2026-07-03 clos par sondes instrumentees : ce n'etait ni TCC ni mlx.
  Causes reelles : transcription 1,3-14,5 s selon pression memoire pendant laquelle
  le focus change d'app, chemins de sortie muets (RMS, texte vide), volume d'entree
  micro 27/100. Details : tasks/todo.md et tasks/lessons.md
- Correctifs livres : garde de focus au collage, message explicite sur chaque
  chemin, alerte volume d'entree < 40 au demarrage. Self-checks verts
  (test_process.py, test_fn_listener.py), boucle re-verifiee live (F8 + say)
- TEST MANUEL FN VALIDE PAR ANTONIN (2026-07-03) : la boucle complete
  fn -> parole -> collage fonctionne au clavier reel. Chantier clos.
- Repo GitHub PUBLIC : https://github.com/antoninmarcon-maker/local-flow
  (note : tasks/ et docs/post-linkedin-2026-07.md y sont publics)

## Restant (ordonne)

1. Post LinkedIn : publication MARDI 2026-07-07 via la routine
   portfolio-weekly-linkedin (8h05). Le pendingDraft pointe deja sur
   drafts/2026-07-07-local-flow.md. Mode validation : la routine ne publie jamais
   seule, Antonin colle le texte a la main. Idealement enregistrer une video demo
   20-30 s avant mardi. Mesure J+3/J+7 dans ~/.claude/voice/engagement-log.md
2. (optionnel) Piste v2 : parakeet-mlx (2x plus rapide, meilleur en francais)
3. (optionnel) Ameliorations README listees dans Pistes d'evolution

## Prochain deblocant

Rien de bloquant : le projet est fonctionnel et publie. A la reprise ("reprends"
dans ce dossier), traiter le Restant 1 (video demo avant le post de mardi 07/07)
ou la piste parakeet-mlx si Antonin le demande.

## Pieges connus

- Premiere inference d'un process : chargement modele ~5-10 s, attendre "Pret.".
  Sous pression memoire une transcription peut prendre 10-20 s ; le terminal
  affiche "transcription en cours..." puis le texte.
- Permissions TCC attachees au host : Terminal pour LocalFlow.command.
- Restauration presse-papiers : texte seulement.
- Tester du collage synthetique pendant que quelqu'un utilise le Mac : les
  evenements partent vers SON app frontale. Verifier
  NSWorkspace.frontmostApplication au moment du post (lecons du 03/07).
