#!/usr/bin/env python3
"""Checks that this computer can run the Streams pipeline. Run from the Streams folder:
    macOS:    .venv/bin/python check_setup.py
    Windows:  .venv/Scripts/python.exe check_setup.py
"""
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_env as env

ok = True


def report(good, label, detail=""):
    global ok
    ok = ok and good
    print(f"  [{'OK' if good else 'MISSING'}] {label}" + (f": {detail}" if detail else ""))


print(f"Streams pipeline setup check ({platform.system()} {platform.machine()}, Python {platform.python_version()})")

# ffmpeg + the filters the pipeline relies on
try:
    v = subprocess.run([env.FFMPEG, "-hide_banner", "-version"], capture_output=True, text=True).stdout.split("\n")[0]
    report(True, "ffmpeg", v)
    filters = subprocess.run([env.FFMPEG, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    for f in ("ass", "loudnorm", "atempo", "alimiter"):
        report(f" {f} " in filters, f"ffmpeg filter '{f}'", "" if f" {f} " in filters else "install a full ffmpeg build (with libass)")
except FileNotFoundError:
    report(False, "ffmpeg", "not found. macOS: brew install ffmpeg | Windows: winget install Gyan.FFmpeg")

# Video encoder: a 1-second test render with captions
enc = env.encoder()
with tempfile.TemporaryDirectory() as d:
    ass = Path(d) / "test.ass"
    ass.write_text("[Script Info]\nScriptType: v4.00+\nPlayResX: 640\nPlayResY: 360\n\n[V4+ Styles]\n"
                   "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
                   "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
                   "MarginR, MarginV, Encoding\nStyle: A,Arial,30,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,"
                   "0,0,1,2,0,2,10,10,10,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
                   "Effect, Text\nDialogue: 0,0:00:00.00,0:00:01.00,A,,0,0,0,,Caption test ’…\n", encoding="utf-8")
    out = Path(d) / "test.mp4"
    r = subprocess.run([env.FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=640x360:r=60:d=1", "-vf", f"ass='{env.ass_path(ass)}'",
                        *env.video_args("4M"), "-pix_fmt", "yuv420p", str(out)], capture_output=True, text=True)
    good = r.returncode == 0 and out.exists() and out.stat().st_size > 0
    note = {"h264_videotoolbox": "Mac hardware encoder (fast)", "h264_nvenc": "NVIDIA GPU encoder (fast)",
            "libx264": "CPU encoder: works, but long videos render slowly"}.get(enc, enc)
    report(good, f"test render with captions using {enc}", note if good else r.stderr.strip()[-300:])

# Python packages
for mod, label in (("whisper", "openai-whisper (transcription)"), ("numpy", "numpy"), ("PIL", "pillow")):
    try:
        __import__(mod)
        report(True, label)
    except ImportError:
        report(False, label, "pip install -r requirements.txt")
try:
    import torch
    gpu = "NVIDIA CUDA" if torch.cuda.is_available() else ("Apple MPS" if getattr(torch.backends, "mps", None)
                                                          and torch.backends.mps.is_available() else "CPU only")
    report(True, "torch", f"{torch.__version__}, {gpu}")
except ImportError:
    report(False, "torch", "installed with openai-whisper")

# Thumbnail font
try:
    report(True, "Impact font", env.font_path("Impact"))
except FileNotFoundError as e:
    report(False, "Impact font", str(e))

if os.name == "nt" and os.environ.get("PYTHONUTF8") != "1":
    print("  [NOTE] PYTHONUTF8 is not set. setup-windows.ps1 sets it; restart the Claude app after setup.")

for d in ("Raw", "Ouput", "work"):
    Path(d).mkdir(exist_ok=True)

print("\nAll set! Put a recording in Raw/ and ask Claude to edit it." if ok else
      "\nSome pieces are missing (see above). Fix them, or ask Claude to fix them, then run this check again.")
sys.exit(0 if ok else 1)
