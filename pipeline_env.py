"""Cross-platform helpers (macOS + Windows) shared by every edit script.

- FFMPEG / FFPROBE: bundled bin/ffmpeg if present, otherwise whatever is on PATH.
- video_args(): the H.264 encoder for this machine.
    macOS   -> h264_videotoolbox (hardware, the original settings)
    Windows -> h264_nvenc if an NVIDIA GPU works, otherwise libx264 (CPU, slower)
  Override with the STREAMS_ENCODER environment variable (videotoolbox / nvenc / libx264).
- ass_path(): a subtitle path that ffmpeg's ass= filter accepts (Windows drive letters need escaping).
- font_path(): Impact / Arial Black / Arial for Pillow-drawn thumbnails.
"""
import functools
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IS_MAC = sys.platform == "darwin"
IS_WIN = os.name == "nt"


def _tool(name):
    for cand in (ROOT / "bin" / name, ROOT / "bin" / f"{name}.exe"):
        if cand.exists():
            return str(cand)
    return shutil.which(name) or name


# Put a bundled bin/ folder (if any) on PATH so libraries that call "ffmpeg" by name (Whisper) find it too.
if (ROOT / "bin").is_dir():
    os.environ["PATH"] = str(ROOT / "bin") + os.pathsep + os.environ.get("PATH", "")

FFMPEG = _tool("ffmpeg")
FFPROBE = _tool("ffprobe")


def _encoder_works(codec):
    try:
        r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                            "color=c=black:s=256x256:d=0.2", "-c:v", codec, "-f", "null", "-"],
                           capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


@functools.lru_cache(maxsize=None)
def encoder():
    forced = os.environ.get("STREAMS_ENCODER", "").strip().lower()
    if forced:
        return {"videotoolbox": "h264_videotoolbox", "nvenc": "h264_nvenc", "x264": "libx264"}.get(forced, forced)
    if IS_MAC:
        return "h264_videotoolbox"
    if _encoder_works("h264_nvenc"):
        return "h264_nvenc"
    return "libx264"


def video_args(bitrate, maxrate=None, bufsize=None):
    """ffmpeg output args from -c:v through -profile:v (callers add -r, -pix_fmt, audio)."""
    enc = encoder()
    rate = ["-b:v", bitrate] + (["-maxrate", maxrate] if maxrate else []) + (["-bufsize", bufsize] if bufsize else [])
    if enc == "h264_nvenc":
        return ["-c:v", enc, "-preset", "p5"] + rate + ["-profile:v", "high"]
    if enc == "libx264":
        return ["-c:v", enc, "-preset", "fast"] + rate + ["-profile:v", "high"]
    return ["-c:v", enc] + rate + ["-profile:v", "high"]


def ass_path(p):
    """Path for use inside ass='...' in a filtergraph.
    Relative to the working directory (the Streams folder) whenever possible, so Windows drive letters ("C:")
    never reach the filter parser. Falls back to an escaped absolute path on a different drive."""
    try:
        s = os.path.relpath(p)
    except ValueError:
        s = str(p)
    s = s.replace("\\", "/")
    if IS_WIN and ":" in s:
        s = s.replace(":", "\\:")
    return s


_FONTS = {
    "Impact": ["/System/Library/Fonts/Supplemental/Impact.ttf", "C:/Windows/Fonts/impact.ttf",
               "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf"],
    "Arial Black": ["/System/Library/Fonts/Supplemental/Arial Black.ttf", "C:/Windows/Fonts/ariblk.ttf"],
    "Arial": ["/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf"],
}


def font_path(name="Impact"):
    for p in _FONTS.get(name, []):
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"Font '{name}' not found. Install it, or add its path to _FONTS in pipeline_env.py.")
