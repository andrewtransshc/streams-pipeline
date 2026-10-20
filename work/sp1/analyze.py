import json, numpy as np
tr=json.load(open("work/sp1/transcript.json"))
scan=np.array(json.load(open("work/sp1/scan.json")))
yel=scan[:,0]
def subs_at(a,b):
    i,j=int(a*2),max(int(a*2)+1,int(b*2)+1); return float((yel[i:j]>0.008).mean()) if i<len(yel) else 0
fmt=lambda s:f"{int(s//3600)}:{int(s%3600//60):02d}:{s%60:05.2f}" if s>=3600 else f"{int(s//60):02d}:{s%60:05.2f}"
lines=[]
for i,s in enumerate(tr["segments"]):
    g=subs_at(s["start"],s["end"])
    lines.append(f"[{i}] {fmt(s['start'])}-{fmt(s['end'])} {'G' if g>0.5 else ' '} {s['text'].strip()}")
open("work/sp1/segments_review.txt","w").write("\n".join(lines))
print(len(lines), sum(len(s['text'].split()) for s in tr['segments']))
