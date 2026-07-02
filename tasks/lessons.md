# Lessons - local-flow

Format : `[date] | ce qui a mal tourne | regle pour l'eviter`

[2026-07-03] | Le self-check affichait 6,6 s de transcription, presque juge trop lent pour l'usage | La premiere inference d'un process inclut le chargement du modele : toujours bencher a chaud (2e/3e run du meme process) avant de juger la latence d'un modele ML. A chaud, turbo fait 1,1 s.
[2026-07-03] | Un modele plus petit semblait suffire au vu de la vitesse | Toujours comparer aussi la qualite sur la langue cible : whisper-small transcrit "Tesla" au lieu de "test" en francais. Vitesse sans precision = inutilisable en dictee.
