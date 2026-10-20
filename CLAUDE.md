# Streams — long-form gameplay edits (YouTube) + Shorts

Lelac's gaming channel. Raw OBS recordings (game full-screen, facecam baked in top-right at x1477 y0 443×321) → full-length YouTube edit with dead air removed, plus vertical Shorts.

Note: the output folder is spelled `Ouput/` (user-created). Each episode gets its own folder, named after the raw file: `Ouput/<raw name>/` (main edit, transcript, captions, upload kit, thumbnails) plus `Ouput/<raw name>/Shorts/`.

## Per-episode steps
1. Raw file in `Raw/`. Pick a short work id (e.g. `sp1`), `mkdir work/<id>`.
2. Extract 16k mono audio → `work/<id>/audio16k.wav`; Whisper `small.en` with word timestamps → `transcript.json` (see `work/sp1/transcribe.py`; needs `PATH="$PWD/bin:$PATH"`). ~3 min for 54 min of audio.
3. 2 fps scan → `scan.json` (`work/sp1/scan.py`): yellow in-game subtitle fraction, motion, brightness. Subtitle presence = game dialogue (not the streamer) and is never cut.
4. Read the transcript, then write `work/<id>/plan.json` (copy `work/sp1/plan.json`): trim start/end, caption speaker overrides (`force_me` / `force_game` / `drop` / `split`), effects, chapters, titles, description, tags, shorts, thumbnails.
5. `PATH="$PWD/bin:$PATH" .venv/bin/python -u stream_edit.py <id> all` (or `docs`, `shorts [n…]`, `main`).

## Settings (first episode, not yet signed off by the user)
- Dead air: silences > 6 s (no speech, no in-game subtitles) are cut down to 1.2 s on each side. Effects are never cut.
- Captions: only the streamer's speech, Arial bold 38, translucent box directly under the facecam, so they don't collide with the game's own bottom-center subtitles. They move under the enlarged cam during cam pops.
- Effects: `cam` = facecam enlarged 2× top-right; `zoom` = 1.35× game punch-in (facecam re-overlaid); `pop` = Impact yellow text with scale-in; `title` = lower-left episode card. SFX are synthesized in `SFX/` (whoosh/boom/pop/ding).
- Audio: +3.4 dB plus a -1.5 dBFS limiter, landing at about -14 LUFS. Micro-fades at every cut.
- **Profanity (Shorts only, the user's choice 2026-10-10):** in Shorts, every swear word (Lelac, Andrew or game) is bleeped: the original audio is muted and a 1 kHz tone plays, 0.25–0.77 s per word. Shorts captions show starred words (f*ck, sh*t, b*tch, a**hole, d*ck). Long videos, transcripts and SRTs stay uncensored. The word list (`CUSS` / `STARS`, `censor`, `find_bleeps`) lives in stream_edit.py and split_fiction_edit.py imports it. Not bleeped: damn, hell, piss, douchebag. Set `"no_bleep": true` in plan.json to turn it off.
- Per-episode overrides in plan.json: `cam` [x,y,w,h] (Part 2 onward uses the smaller 1550,0,370,268 facecam and a headset mic) and `audio_gain_db` (Part 2: +2.0, source −16 LUFS). Speaker labels for Part 2+ come from `work/sp2/voiceid.py` (ECAPA, Lelac vs game centroids, `.venv-voice`) plus regexes for repeated combat lines.
- **Speed:** South Park long videos play at 1.1x (`MAIN_SPEED` in stream_edit.py; `"main_speed"` in plan.json overrides it), with pitch-preserving atempo. The transcript, SRT, chapters and final length in the upload kit are scaled to match. Shorts stay at 1.0x. Split Fiction is unchanged (1.0x).
- Main export: h264_videotoolbox 16 Mbps 1080p60, AAC 320k. Shorts: 1080×1920, facecam on top (782 px) and game crop below (1138 px), all dialogue captioned (game lines in yellow), hook pill for the first 3.2 s.

## Thumbnails
`work/<id>/thumb/make_thumb.py` (Copycat: `work/cc2/thumb/make_thumbs.py` builds all three, cutouts from `cutouts.py`) composites cutouts in 1280×720 (sunburst background, white outlines, Impact text). Cutouts come from rembg `isnet-general-use`, installed in a separate venv. **Always pass `providers=["CPUExecutionProvider"]`**: the default CoreML provider hangs forever on this Mac. With CPU each cutout takes about 2 s. `isnet-anime` and `u2net` fail on South Park characters.

## Per-game projects
Each game has its own edit script, so its settings can change without touching the other games:
- **South Park: The Stick of Truth** → `stream_edit.py` (work ids `sp1`, …). Solo, full-screen game, yellow subtitles.
- **Split Fiction** → `split_fiction_edit.py` (work ids `sf1`, …). Co-op split-screen, Lelac + Andrew both on cam.
- **Copycat** → `copycat_edit.py` (work ids `cc0` = FaceMask pre-show, `cc1` = Part 1 (Intro), `cc2` = Part 2, …). Solo, same settings as South Park (1.1x long video, Shorts bleeped).

### Split Fiction specifics (sf1)
- Facecam x1550 y0 370×268. Game subtitles are white text bottom-center (letterbox in cutscenes, italic over gameplay).
  `work/sf1/subscan.py` scans that band at full res → `subs.npy`, merged into `scan.json` column 0 (cutoff 0.005).
  `scan.py` also stores left/right-half motion (cols 3/4) used by `side: "auto"`.
- Speakers: audio is one mixed track. `diarize.py` (run with `.venv-voice/bin/python`, which has SpeechBrain) embeds
  1.5 s windows with ECAPA, 2-way clusters the subtitle-free ones (higher pitch = Lelac), and flags low-similarity
  windows as game voices → `voice_prob.json`. About half the talking is each of them (confirmed by Andrew).
  Facecam mouth-motion (`mouths.py`) was tried as a teacher and was unreliable. Lelac's face moves a lot while listening.
  Speaker labels are best effort. Fix them per segment in plan.json: `force_lelac` / `force_andrew` / `force_game`,
  `not_game` (streamer talking over subtitles), `drop`.
- Captions: Lelac white, Andrew light blue (`&H00FFD27A`); game lines are not captioned in the main edit.
- Zooms and Shorts take `side`: `C` (full screen or cutscene), `L`, `R`, or `auto`. Check visually. Some fantasy
  sections switch to a single full screen, where `C` is right. The Shorts `R` crop sits below the facecam.
- Thumbnail ideas in plan.json can use `{T:<raw seconds>}`, which is converted to "edit [raw]" times in the upload kit.
- Whisper hears "Lelac" as "Leela", "Rader" as "Raider", and her gamer tag **BaoChickaWowWow** as "Bauchika Wow Wow". Fixes go in plan.json `fixes` (South Park: `word_merge` for phrases that span several words).
- Game audio (sf1): the DJI mics picked up the game from the room, so it sat ~21 dB under the voices. Fix:
  Demucs (`.venv-voice`, `-n htdemucs --two-stems=vocals -d mps`, ~15 min per hour) → `work/sf1/game_boost.py`:
  no_vocals +10 dB; game-dialogue spans in vocals lifted toward -21 dBFS (max +10 dB, never boosts speech already
  at speaking level); written 10 dB down for headroom → `audio/game_boost.wav`. plan.json `audio_src` points the
  renders at it, and `audio_gain_db` 8.3 lands Shorts and `main_audio_gain_db` 9.9 lands the long video at ~-14 LUFS. (The South Park +3.4 dB default is wrong
  for this raw, which is already -13 LUFS.) If future recordings capture game audio directly, drop `audio_src`.

### Copycat specifics (cc0–cc2)
- Facecam x1550 y0 370×268. Subtitles sit bottom centre (y ~1000–1040) in a translucent dark box, and the speaker name
  colour varies (Olive yellow, Nature Expert green, neighbours grey), so detection uses the white-text fraction
  (scan col 3, `SUB_TH` 0.004; `work/cc0/scan.py <id> <raw>`). Bright floors and tiles cause false hits. List them in plan.json `not_subs`.
- The cat's thoughts appear as big handwritten text in the world. Lelac reads them aloud, so they count as her speech.
  Game vs Lelac labels are set by hand per segment (`force_me` / `force_game` / `drop`), plus `fixes` for names (Whisper hears Dawn as "Don").
- Copycat has long silent story cutscenes (car ride, Olive leaving, dreams). Protect them from the dead-air cut with plan.json `keep` ranges.
- Raw loudness differs per file, so set `audio_gain_db` per episode (cc0 +3.4, cc1 −1.4, cc2 +5.5).
- Recording order: Part 1 (Intro) → FaceMask pre-show → Part 2. Whisper uses `work/cc0/transcribe.py <ids…>` with a Copycat prompt.
