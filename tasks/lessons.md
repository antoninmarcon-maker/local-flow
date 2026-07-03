# Lessons - local-flow

Format : `[date] | ce qui a mal tourne | regle pour l'eviter`

[2026-07-03] | Le self-check affichait 6,6 s de transcription, presque juge trop lent pour l'usage | La premiere inference d'un process inclut le chargement du modele : toujours bencher a chaud (2e/3e run du meme process) avant de juger la latence d'un modele ML. A chaud, turbo fait 1,1 s.
[2026-07-03] | Un modele plus petit semblait suffire au vu de la vitesse | Toujours comparer aussi la qualite sur la langue cible : whisper-small transcrit "Tesla" au lieu de "test" en francais. Vitesse sans precision = inutilisable en dictee.
[2026-07-03] | "Le texte ne se colle pas" attribue a tort a TCC puis a mlx : 3 sondes de collage ont echoue parce que l'utilisateur travaillait dans Chrome pendant les tests, le Cmd+V partait vers SON app frontale | Tout test de collage/CGEventPost sur une machine en usage doit capturer NSWorkspace.frontmostApplication au moment exact du post ; un event tap observateur (touche neutre F15) prouve la delivrance sans dependre du focus ni polluer les apps.
[2026-07-03] | Deux chemins de sortie muets (garde RMS, texte vide) + transcription 1,3-14,5 s selon la pression memoire = bug indiagnosticable a distance | Aucun chemin de sortie silencieux dans une app interactive : chaque return doit imprimer pourquoi, et toute etape > 1 s doit annoncer qu'elle commence ("transcription en cours...").
[2026-07-03] | Le collage partait vers l'app frontale du moment, pas celle de la dictee (transcription lente sous pression memoire) | Capturer la cible au declenchement (relachement de touche) et re-verifier avant d'agir ; si la cible a change, degrader proprement (presse-papiers + message) plutot qu'agir a l'aveugle.
