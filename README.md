# Streams: gameplay video editor for Claude Code

Turns a long OBS gameplay recording (game full-screen, facecam in a corner) into:

- a **YouTube video** with dead air cut, captions, zooms, text pop-ups, sound effects and level audio
- **vertical Shorts** of the best moments (facecam on top, gameplay below, swearing bleeped)
- a **transcript**, a **captions file**, an **upload kit** (titles, description, chapters, tags) and **thumbnail ideas**

You don't run the scripts yourself. You talk to Claude in Claude Code, and it uses this folder to do the editing.

Works on **macOS** (Apple Silicon or Intel) and **Windows 10/11**.

---

## What you need

- A **Claude Pro or Max** plan
- **macOS**, or **Windows 10/11** (an NVIDIA graphics card is strongly recommended on Windows. Without one, rendering a 1-hour video takes 1–2 hours.)
- 16 GB RAM and about 50 GB free disk space
- If this repository is private: a GitHub account, and accept the invite the owner sends you

## Install

### 1. Windows only: install Git
Download **Git for Windows** from https://git-scm.com/download/win and run the installer, clicking **Next** through every screen (the defaults are fine).

### 2. Install the Claude app
Download it from https://claude.ai/download, open it, sign in, and click the **Code** tab at the top.

### 3. Let Claude set everything up
In the Code tab, choose your **Documents** folder as the working folder, then paste this message:

> Clone https://github.com/andrewtransshc/streams-pipeline into my Documents folder as "Streams", then run its setup script for this computer (setup-mac.sh on a Mac, setup-windows.ps1 on Windows) and tell me what check_setup.py reports.

- Claude asks before running each command. Click **Allow**.
- **Mac:** if Homebrew gets installed, you'll be asked for your Mac password. Type it yourself in the terminal window.
- **Windows:** click **Yes** on any "allow this app to make changes" pop-ups.
- If Claude asks you to sign in to GitHub, follow its prompts.
- This takes about 10–30 minutes, mostly downloading.
- **Windows:** when it finishes, **close and reopen the Claude app** so it picks up the newly installed tools.

### 4. Open the project
In the Code tab, switch the working folder to **Documents/Streams**. Claude now reads the project's instructions automatically.

## Edit a video

1. Put your OBS recording (`.mp4`, 1080p60 is ideal) in `Streams/Raw/`.
2. Tell Claude, for example:
   > There's a new gameplay video in Raw. Edit it like the South Park episodes: cut dead air, add captions, zooms and sound effects, and make Shorts. My facecam is in the top-right corner, my name is ___ and my channel is ___.
3. Finished files appear in `Streams/Ouput/<video name>/`, with Shorts in the `Shorts` subfolder.
4. Give feedback by timestamp, like *"at 21:20 the fight has too many cuts"* or *"make the captions bigger"*, and Claude re-renders.

## Tips

- Keep your computer awake while it renders (Mac: plug in. Windows: Settings → System → Power → sleep **Never** while plugged in).
- Tell Claude your name, gamer tag and any words the transcription gets wrong. It fixes them in every episode after that.
- Optional extras, speaker detection (your voice vs. game characters vs. a co-op partner) and automatic thumbnail cutouts, need one more install. Ask Claude to "run the setup script with extras".
- Something not working? Ask Claude to run `check_setup.py` and fix whatever it reports.

## What's in here

| Path | What it is |
| --- | --- |
| `CLAUDE.md` | Claude's instructions for this project (workflow, settings, lessons learned) |
| `stream_edit.py` | Main editor (solo full-screen games, e.g. South Park) |
| `split_fiction_edit.py` | Editor for co-op split-screen games |
| `copycat_edit.py` | Editor variant used for Copycat |
| `pipeline_env.py` | Picks ffmpeg, the video encoder and fonts for Mac or Windows |
| `setup-mac.sh`, `setup-windows.ps1`, `check_setup.py` | Install and verify |
| `SFX/` | Sound effects (whoosh, boom, pop, ding) |
| `work/<episode>/` | Per-episode plans and helper scripts (examples to copy) |
| `Raw/`, `Ouput/` | Your recordings and finished videos (not uploaded to GitHub) |
