# Full-res subtitle band scan, 2 fps -> subs.npy: fraction of "text-like" white pixels
# (white with a dark pixel within 3 px horizontally) in y960-1060, x240-1680.
import subprocess, numpy as np
X0, Y0, W, H = 240, 960, 1440, 100
p = subprocess.Popen(["bin/ffmpeg", "-v", "error", "-i", "Raw/Split Fiction Part 1.mp4", "-vf",
                      f"fps=2,crop={W}:{H}:{X0}:{Y0}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
out = []
while True:
    b = p.stdout.read(W * H * 3)
    if len(b) < W * H * 3: break
    f = np.frombuffer(b, np.uint8).reshape(H, W, 3).astype(np.int16)
    white = (f.min(2) > 180) & ((f.max(2) - f.min(2)) < 40)
    dark = f.max(2) < 50
    near = np.zeros_like(dark)
    for k in (1, 2, 3):
        near[:, k:] |= dark[:, :-k]; near[:, :-k] |= dark[:, k:]
    out.append(float((white & near).mean()))
np.save("work/sf1/subs.npy", np.array(out, np.float32)); print(len(out))
