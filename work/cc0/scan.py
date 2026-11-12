# 2 fps scan -> scan.json rows [yellow_sub_frac, motion, brightness, white_sub_frac]
# Copycat subtitles: yellow speaker name + white line, bottom centre (y ~1000-1035 at 1080p).
import os, sys; sys.path.insert(0, os.getcwd())  # run from the Streams folder
from pipeline_env import FFMPEG
import subprocess, numpy as np, json, sys
W, H = 960, 540
wid, raw = sys.argv[1], sys.argv[2]
p = subprocess.Popen([FFMPEG, "-v", "error", "-i", raw, "-vf", f"fps=2,scale={W}:{H}", "-f", "rawvideo",
                      "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
prev = None; out = []
while True:
    b = p.stdout.read(W * H * 3)
    if len(b) < W * H * 3: break
    f = np.frombuffer(b, np.uint8).reshape(H, W, 3).astype(np.int16)
    game = f[:, :int(W * 0.8)]
    band = f[496:520, int(W * 0.2):int(W * 0.8)]
    yellow = ((band[..., 0] > 180) & (band[..., 1] > 150) & (band[..., 2] < 90)).mean()
    white = ((band.min(2) > 225)).mean()
    g = game.mean(2)
    motion = 0.0 if prev is None else float(np.abs(g - prev).mean())
    prev = g
    out.append([round(float(yellow), 4), round(motion, 2), round(float(g.mean()), 1), round(float(white), 4)])
json.dump(out, open(f"work/{wid}/scan.json", "w")); print(wid, len(out))
