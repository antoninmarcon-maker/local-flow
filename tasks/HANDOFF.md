---
statut: pret-a-valider
auto-resume: false
updated: 2026-07-03T12:20:00+02:00
---

# HANDOFF - local-flow

## Objectif

Dictee vocale 100 % locale (clone Wispr Flow) operationnelle sur le M2 8 GB :
maintenir fn, parler, relacher, le texte se colle dans l'app active.

## Fait (verifie)

- App complete sur main (pipeline mlx-whisper turbo, fn via event tap Quartz,
  annulation combo, garde RMS, dictionnaire, collage Cmd+V + restauration)
- DEBUG DU 2026-07-03 TERMINE, cause racine trouvee par sondes instrumentees :
  - Permissions Terminal TOUTES accordees (Accessibilite verifiee par sonde
    AXIsProcessTrusted DANS Terminal : true ; Surveillance de l'entree : tap cree ;
    micro : echantillons reels captes). Ce n'etait PAS un probleme TCC.
  - Le collage CGEventPost fonctionne, y compris apres inference mlx (verifie par
    event tap observateur : 10/10 evenements F15 recus avant ET apres mlx).
  - Les vrais coupables : (1) transcription 1,3 s a 14,5 s selon la pression
    memoire -> pendant ce delai muet l'utilisateur change d'app et le Cmd+V part
    vers la mauvaise app ; (2) deux chemins de sortie silencieux (garde RMS,
    texte vide) ; (3) volume d'entree micro a 27/100, proche du seuil RMS 0.005
    (l'ambiance mesure 0.0035).
  - Correctifs commites : garde de focus (app cible capturee au relachement, si
    le focus a change -> texte dans le presse-papiers + message, jamais de collage
    aveugle), message explicite sur CHAQUE chemin (silence avec valeur RMS, trop
    court, vide, annulation, "transcription en cours...", "colle dans X"),
    alerte volume d'entree < 40 au demarrage.
  - Self-checks verts : test_process.py (4 chemins), test_fn_listener.py.
    Boucle complete re-verifiee en live (F8 synthetique + say) : transcription
    1,3 s, collage vers l'app frontale correcte.
- Repo GitHub public : voir tasks/todo.md (etape publication)

## Restant (ordonne)

1. Test manuel fn par Antonin (2 min) : lancer LocalFlow.command, Notes au premier
   plan, maintenir fn, dire une phrase, relacher, REGARDER LE TERMINAL : chaque
   issue affiche maintenant un message qui dit quoi faire (voir README Depannage).
2. Monter le volume d'entree micro au-dessus de 40/100 (Reglages > Son > Entree),
   il est a 27 : l'app le signale au demarrage.
3. Si un cas reste muet : c'est un bug, le rapporter avec la sortie du terminal.
4. Post LinkedIn : publication MARDI 2026-07-07 via routine portfolio-weekly-linkedin
   (8h05), pendingDraft deja pointe sur drafts/2026-07-07-local-flow.md. AVANT mardi :
   valider le test fn + idealement video demo 20-30 s. NOTE : le brouillon
   docs/post-linkedin-2026-07.md est desormais PUBLIC sur le repo GitHub.
5. Piste v2 : parakeet-mlx (2x plus rapide, meilleur en francais).

## Pieges connus

- La premiere inference d'un process charge le modele (~5-10 s) : attendre "Pret.".
  Sous pression memoire (Chrome + Claude ouverts), une transcription peut prendre
  10-20 s ; le terminal affiche desormais "transcription en cours..." puis le texte.
- Les permissions TCC sont attachees au host : Terminal pour LocalFlow.command.
- Restauration presse-papiers : texte seulement.
- Pour tester le collage par script : l'app frontale peut changer si quelqu'un
  utilise le Mac pendant le test -> les evenements partent ailleurs. Toujours
  verifier NSWorkspace.frontmostApplication au moment du post (lecon du 03/07 :
  3 sondes ont accuse a tort TCC puis mlx alors que le focus etait sur Chrome).
