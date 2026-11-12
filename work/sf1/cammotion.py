# Facecam motion per person at 10 fps -> cam_motion.npy [N,2] (Lelac left part, Andrew right part of cam)
import os, sys; sys.path.insert(0, os.getcwd())  # run from the Streams folder
from pipeline_env import FFMPEG
import subprocess, numpy as np
W, H = 185, 134
p = subprocess.Popen([FFMPEG, "-v", "error", "-i", "Raw/Split Fiction Part 1.mp4", "-vf",
     f"fps=10,crop=370:268:1550:0,scale={W}:{H},format=gray", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
prev, out = None, []
while True:
    b = p.stdout.read(W * H)
    if len(b) < W * H: break
    g = np.frombuffer(b, np.uint8).reshape(H, W).astype(np.int16)
    if prev is None: out.append([0, 0])
    else:
        d = np.abs(g - prev)
        out.append([float(d[25:, :98].mean()), float(d[25:, 102:].mean())])
    prev = g
np.save("work/sf1/cam_motion.npy", np.array(out, np.float32)); print(len(out))
