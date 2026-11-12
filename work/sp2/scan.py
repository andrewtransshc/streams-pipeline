import os, sys; sys.path.insert(0, os.getcwd())  # run from the Streams folder
from pipeline_env import FFMPEG
import subprocess, numpy as np, json
W,H=384,216
p=subprocess.Popen([FFMPEG,"-v","error","-i","Raw/South Park Stick of Truth Part 2.mp4","-vf",f"fps=2,scale={W}:{H}","-f","rawvideo","-pix_fmt","rgb24","-"],stdout=subprocess.PIPE)
prev=None; out=[]
while True:
    b=p.stdout.read(W*H*3)
    if len(b)<W*H*3: break
    f=np.frombuffer(b,np.uint8).reshape(H,W,3).astype(np.int16)
    game=f[:, :int(W*0.77)]  # exclude facecam column roughly
    band=f[int(H*0.86):int(H*0.945), int(W*0.2):int(W*0.8)]
    yellow=((band[...,0]>190)&(band[...,1]>140)&(band[...,2]<90)).mean()
    g=game.mean(2)
    motion=0.0 if prev is None else float(np.abs(g-prev).mean())
    prev=g
    out.append([round(float(yellow),4),round(motion,2),round(float(g.mean()),1)])
json.dump(out,open("work/sp2/scan.json","w")); print(len(out))
