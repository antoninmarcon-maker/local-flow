# Etude : architecture de Wispr Flow

Etude realisee le 2026-07-03 (agent de recherche web) pour concevoir local-flow.
Synthese en francais, rapport detaille en anglais ensuite.

## Synthese

- **Boucle UX** : maintenir fn (Mac), parler, relacher -> texte formate colle au curseur.
  Indicateur visuel (pilule avec forme d'onde) + son. Latence pipeline < 700 ms p99
  (percue : 1 a 2 s). Mode mains libres en double-tap, mode commande (fn+Ctrl) pour
  reecrire une selection.
- **Architecture** : client desktop (Electron cote Windows, probable cote Mac, ~800 MB RAM),
  capture audio locale, mais **tout le reste est cloud** : ASR par ensemble de modeles
  (famille Whisper + autres, selection par langue) sur Baseten/AWS, couche de formatage par
  Llama fine-tune (suppression des fillers, ponctuation, ton par app, auto-corrections
  "non attends, plutot mardi"). Le texte peut transiter par OpenAI/Anthropic/Cerebras.
- **Insertion du texte** : permission Accessibilite macOS, collage au curseur
  (presse-papiers + evenements clavier), pas de frappe caractere par caractere.
- **Privacy** : rien n'est on-device sauf capture et UI. "Privacy Mode" = retention zero,
  mais l'audio quitte toujours la machine (garantie contractuelle, pas architecturale).
  Incident 2025 : captures d'ecran de la fenetre active envoyees au cloud.
- **Features coeur a repliquer** : hotkey globale hold-to-talk, collage au curseur,
  auto-ponctuation + suppression des fillers, dictionnaire personnel, indicateur
  d'enregistrement, multilingue avec auto-detection.
- **Pattern commun des clones open source** (VoiceInk, Handy, whisper-writer, OpenWhispr,
  Frespr) : enregistrer pendant que la touche est maintenue -> VAD -> inference locale
  Whisper/Parakeet -> presse-papiers -> Cmd+V simule -> restauration du presse-papiers.
- **Recos cles pour un clone local Apple Silicon** : mlx-whisper large-v3-turbo (MLX bat
  faster-whisper sur M-series, qui n'a pas Metal), parakeet-mlx encore plus rapide et
  meilleur en francais (piste v2), garde VAD/RMS contre les hallucinations Whisper sur
  silence ("Sous-titres par Amara.org"), prechargement du modele au demarrage,
  restauration du presse-papiers apres 150-300 ms, champs secure input non dictables.

## Rapport detaille (agent, 2026-07-03)

### 1. UX Loop

**Push-to-talk (default):** Hold the **Fn key** on Mac (Ctrl+Win on Windows), speak,
release to finish. On press you get an audio ping and an on-screen indicator (a small
pill/bar at the bottom of the screen with animated waveform bars). Release -> formatted
text is pasted at the cursor position in whatever app has focus.

**Hands-free / toggle mode:** Double-tap the dictation hotkey, or press Fn+Space, to
start dictation without holding; press Fn again to stop and paste.

**Command Mode:** Hold Fn+Ctrl, speak an instruction. If text is selected, Flow rewrites
the selection ("make this more concise"); with no selection the AI response is inserted
at the cursor. Paid tier only.

**Hotkeys rebindable** (up to 4 bindings per action, mouse buttons 4-10 supported,
Caps Lock restricted on Mac).

**Latency:** Baseten claims the entire pipeline (ASR + Llama formatting) completes in
under 700 ms at p99; users report 1-2 s perceived latency.

Sources: docs.wisprflow.ai (starting-your-first-dictation, use-flow-hands-free,
how-to-use-command-mode, supported-unsupported-keyboard-hotkey-shortcuts),
baseten.co/resources/customers/wispr-flow/

### 2. Technical Architecture

- **Client:** cross-platform desktop app. Windows build confirmed Electron (~800 MB RAM
  idle); Mac build probably Electron too (unconfirmed), same memory footprint reported.
- **ASR: cloud, always.** "Transcription always occurs on the cloud" (Wispr docs).
  Ensemble of speech recognition models (Whisper-family plus newer engines), dynamic
  selection of the best ASR engine per language, accent confidence scoring.
- **Formatting layer: fine-tuned Llama models hosted on Baseten** (AWS us-east-1).
  Removes filler words, punctuates, formats lists, applies app-aware tone, learns from
  user edits. Text may be routed to OpenAI, Anthropic, Cerebras.
- **Context capture:** reads active app name (and historically captured screenshots of
  the active window, sent to cloud); can read keystrokes to learn from corrections.
- **Text insertion on macOS:** requires Accessibility permission; paste-at-cursor
  (clipboard + simulated keyboard events) rather than character-by-character typing.
- **Requires internet, no offline mode.**

Sources: wisprflow.ai/data-controls, wisprflow.ai/research/supporting-languages,
baseten.co, spokenly.app/blog/wispr-flow-review, en.wikipedia.org/wiki/Wispr_Flow

### 3. Cloud vs on-device, privacy model

On-device: essentially nothing but capture and UI. All ASR and LLM formatting are cloud.
Privacy Mode: zero data retention, training opt-in (off by default), SOC 2 / HIPAA /
ISO 27001. 2025 incident: active-window screenshots shipped to cloud alongside audio;
Privacy Mode added afterwards. Structural criticism: even with Privacy Mode, audio always
leaves the machine; privacy is contractual, not architectural.

Sources: docs.wisprflow.ai/articles/6274675613-privacy-mode-data-retention,
modelpiper.com/blog/wispr-flow-privacy-incident, getvoibe.com/resources/is-wispr-flow-safe/

### 4. Feature inventory (ranked)

Core: 1) global push-to-talk + hands-free toggle, works in any app; 2) paste-at-cursor,
formatted, 1-2 s perceived; 3) auto-formatting (fillers, punctuation, self-corrections,
lists); 4) personal dictionary (manual + learned); 5) recording indicator + audio cue;
6) multilingual (104 languages; Wispr recommends pinning a small language pool; French
support includes narrow space before ?/!).

Second tier: 7) tone matching per app; 8) Command Mode; 9) Whisper Mode (quiet speech).

Nice-to-have: snippets, history, sync, code-switching, team controls.

### 5. Open-source local alternatives

| Project | Stack | STT | Hotkey | Injection macOS |
|---|---|---|---|---|
| VoiceInk (GPL-3) | Swift natif | whisper.cpp + Parakeet CoreML | KeyboardShortcuts lib | CGEvent / AX, permission Accessibilite |
| Handy (MIT, ~23k stars) | Tauri Rust + React | whisper.cpp + Parakeet (transcribe-rs), Silero VAD | rdev (Globe key en cours) | collage presse-papiers, enigo en fallback |
| whisper-writer | Python + PyQt5 | faster-whisper | pynput (hold/toggle/VAD) | pynput frappe par caractere (plus fragile) |
| OpenWhispr (MIT) | Electron | whisper.cpp + sherpa-onnx | hotkey globale | simulation de collage |
| Frespr (AGPL) | Swift natif | cloud Gemini (BYOK) | 5 options, defaut Option droite | AX direct, collage en fallback |

Pattern commun : record pendant hold -> VAD -> inference locale -> clipboard ->
Cmd+V simule -> restauration presse-papiers.

### 6. Recommendations for a minimal local clone (Python, Apple Silicon)

- **STT:** mlx-whisper large-v3-turbo par defaut (MLX >> faster-whisper sur M-series,
  CTranslate2 n'a pas Metal). parakeet-mlx ~2x plus rapide et bat Whisper en francais
  (WER 12.0 vs 12.6) mais pinning de langue plus faible : bonne piste v2.
- **Injection:** clipboard + Cmd+V simule (CGEvent), pas de frappe par caractere
  (accents francais fragiles). Restaurer le presse-papiers apres ~150-300 ms.
  Upgrade possible : insertion AX directe (kAXSelectedTextAttribute), compatibilite
  par app inegale.
- **Hotkey:** fn/Globe non capturable simplement en userspace ; Option droite ou F-key.
- **Pitfalls:** permission Accessibilite attachee au terminal hote ; permission micro
  separee (TCC) ; champs secure input avalent les frappes synthetiques ; race de
  restauration du presse-papiers ; hallucinations Whisper sur silence (VAD/RMS
  obligatoire) ; premier chargement MLX lent (precharger au demarrage) ; couche LLM
  optionnelle (Whisper turbo ponctue deja, ~80 % de la valeur percue).
