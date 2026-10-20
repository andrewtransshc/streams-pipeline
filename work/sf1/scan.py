# Split Fiction scan, 2 fps: [white subtitle fraction, motion, brightness, motion_left, motion_right]
# Game subtitles are small white text, bottom-center. Facecam (x1550 y0 370x268) excluded from motion.
import subprocess, numpy as np, json
W,H=384,216
p=subprocess.Popen(["bin/ffmpeg","-v","error","-i","Raw/Split Fiction Part 1.mp4","-vf",f"fps=2,scale={W}:{H}","-f","rawvideo","-pix_fmt","rgb24","-"],stdout=subprocess.PIPE)
prev=None; out=[]
while True:
    b=p.stdout.read(W*H*3)
    if len(b)<W*H*3: break
    f=np.frombuffer(b,np.uint8).reshape(H,W,3).astype(np.int16)
    band=f[int(H*0.885):int(H*0.975), int(W*0.25):int(W*0.75)]
    white=((band.min(2)>185)&((band.max(2)-band.min(2))<30)).mean()
    g=f.mean(2); g[:int(H*0.25), int(W*0.805):]=0
    if prev is None: m=ml=mr=0.0
    else:
        d=np.abs(g-prev); m=float(d.mean()); ml=float(d[:, :W//2].mean()); mr=float(d[:, W//2:].mean())
    prev=g
    out.append([round(float(white),4),round(m,2),round(float(g.mean()),1),round(ml,2),round(mr,2)])
json.dump(out,open("work/sf1/scan.json","w")); print(len(out))
