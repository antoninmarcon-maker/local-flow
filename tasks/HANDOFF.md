---
statut: bloque
auto-resume: false
updated: 2026-07-03T01:20:00+02:00
---

# HANDOFF - local-flow

## Objectif

Dictee vocale 100 % locale (clone Wispr Flow) operationnelle sur le M2 8 GB :
maintenir fn, parler, relacher, le texte se colle dans l'app active.
Il ne reste qu'a valider la boucle complete au clavier reel.

## Fait (verifie)

- App complete commitee sur main : pipeline mlx-whisper large-v3-turbo (1,1 s a chaud,
  FR parfait au self-check), touche fn par defaut via event tap Quartz, annulation si
  autre touche pendant l'enregistrement, garde RMS anti-hallucination, dictionnaire
  personnel, collage Cmd+V + restauration presse-papiers
- Self-checks verts : tests/test_pipeline.py (FR + EN) et tests/test_fn_listener.py
  (machine a etats fn par CGEvents synthetiques)
- Lanceurs : LocalFlow.command + ~/Applications/LocalFlow.app (Spotlight l'indexe).
  LaunchAgent launchd DESINSTALLE (choix Antonin : RAM juste, ~2,3 GB residents),
  script conserve dans scripts/install-launchagent.sh
- Etude architecture Wispr : docs/wispr-flow-architecture.md
- Debug fn commence (2026-07-03 tard le soir) :
  - Instance lancee par Antonin a 01:09 avec le bon code (commit fn 01:05), le tap
    Quartz s'est cree -> Surveillance de l'entree OK pour son host
  - Touche globe reglee sur "Ne rien faire" (defaults write com.apple.HIToolbox
    AppleFnUsageType -int 0, FAIT)
  - Pas de secure input actif ; dictee Apple ACTIVEE (conflit possible)
  - TCC Accessibilite/Micro pour Terminal : non verifiables sans Full Disk Access,
    c'est la zone suspecte

## Restant (ordonne)

1. Test manuel 4 observations (voir Prochain deblocant) - Antonin, demain
2. Selon la matrice de diagnostic : accorder la permission manquante ou debugger le code
3. Si une popup dictee Apple apparait sur fn : desactiver la dictee Apple
   (Reglages Systeme > Clavier > Dictee)
4. Apres validation : mettre a jour tasks/todo.md, cloturer le run, evoquer la piste v2
   parakeet-mlx (2x plus rapide, meilleur en francais)
5. Apres validation : publier le post LinkedIn (brouillon pret dans
   docs/post-linkedin-2026-07.md, routine R4) avec une video de demo de 20-30 s,
   puis mesurer a J+3/J+7 dans ~/.claude/voice/engagement-log.md

## Prochain deblocant

A la reprise ("reprends" dans ce dossier) :

1. S'assurer qu'une fenetre Terminal LocalFlow affiche "Pret." (sinon Spotlight > LocalFlow).
2. Relancer l'ecouteur temoin fn en arriere-plan (session Claude) :

```bash
cd ~/Documents/Projects/local-flow && uv run python -u - > /tmp/fn-echo.log 2>&1 <<'EOF' &
import time
from localflow.app import FnListener
listener = FnListener(
    on_press=lambda: print(f"{time.strftime('%H:%M:%S')} FN DOWN", flush=True),
    on_release=lambda: print(f"{time.strftime('%H:%M:%S')} FN UP", flush=True),
    on_cancel=lambda: print(f"{time.strftime('%H:%M:%S')} CANCEL", flush=True),
)
listener.prepare()
print("echo listener pret", flush=True)
listener.run()
EOF
```

3. Test d'Antonin : dans Notes, maintenir fn, dire "ceci est un test", relacher.
   Observer : (a) sons Tink/Pop ; (b) nouvelle ligne dans le Terminal LocalFlow ;
   (c) texte colle dans Notes ; (d) interface Apple ouverte (dictee, emoji).
4. Matrice de diagnostic (lire /tmp/fn-echo.log en plus des reponses) :
   - fn-echo VIDE apres le test -> les evenements fn ne circulent pas : re-verifier
     Surveillance de l'entree du host, relancer l'app apres octroi
   - Sons + ligne transcrite dans le Terminal + RIEN dans Notes -> Accessibilite
     manquante pour Terminal (le collage CGEvent est avale) : l'ajouter, relancer
   - Sons + AUCUNE ligne dans le Terminal -> micro refuse (silence -> garde RMS) :
     Reglages > Confidentialite > Microphone > Terminal
   - Popup dictee Apple -> desactiver la dictee Apple, re-tester
5. Ne pas oublier de tuer l'ecouteur temoin apres le debug (pgrep -f "uv run python -u").

## Pieges connus

- La premiere inference d'un process charge le modele (~5-6 s) : attendre "Pret."
  avant de juger. Bencher a chaud, jamais sur le run 1.
- Les permissions TCC sont attachees au host : Terminal pour LocalFlow.command,
  binaire python du framework pour le LaunchAgent (desinstalle).
- L'instance du soir est restee ouverte dans une fenetre Terminal (pid 22798 le
  2026-07-03) : fermer la fenetre libere ~2,3 GB.
- defaults AppleFnUsageType peut necessiter une deconnexion/reconnexion pour etre
  pris en compte par toutes les surfaces systeme.
- Restauration presse-papiers : texte seulement, une image copiee juste avant la
  dictee est perdue.
