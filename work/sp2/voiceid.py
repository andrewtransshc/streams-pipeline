# Lelac vs game voice per transcript segment (ECAPA embeddings). Run with .venv-voice/bin/python.
import json, wave, numpy as np, torch
w = "work/sp2"
x = np.frombuffer(wave.open(f"{w}/audio16k.wav").readframes(10**9), np.int16).astype(np.float32) / 32768
tr = json.load(open(f"{w}/transcript.json"))
from speechbrain.inference.speaker import EncoderClassifier
enc = EncoderClassifier.from_hparams("speechbrain/spkrec-ecapa-voxceleb", savedir="pretrained/ecapa", run_opts={"device": "cpu"})
idx, clips = [], []
for i, s in enumerate(tr["segments"]):
    ws = [q for q in s["words"] if q["word"].strip()]
    if not ws: continue
    a, b = ws[0]["start"], ws[-1]["end"]
    if b - a < 0.6: a, b = a - (0.6 - (b - a)) / 2, b + (0.6 - (b - a)) / 2
    b = min(b, a + 6)
    idx.append(i); clips.append(torch.tensor(x[max(0, int(a * 16000)):int(b * 16000)]))
E = []
for k in range(0, len(clips), 32):
    batch = clips[k:k + 32]; L = max(len(q) for q in batch)
    wav = torch.stack([torch.nn.functional.pad(q, (0, L - len(q))) for q in batch])
    with torch.no_grad(): E.append(enc.encode_batch(wav, torch.tensor([len(q) / L for q in batch])).squeeze(1).numpy())
E = np.concatenate(E); E /= np.linalg.norm(E, axis=1, keepdims=True)
pos = {i: k for k, i in enumerate(idx)}
lelac = [2,3,4,5,6,7,10,31,32,37,38,39,103,109,114,115,116,203,208,247,248,249,530,544,548,549,556,557,575,977,978,979,980,981,982,983,984,985,986,987,989]
game = list(range(15,22)) + [91,94,158,159,160,399,581,679,680,682,683,684,685,686,687] + list(range(747,756)) + list(range(757,771)) + [908,941] + list(range(958,966))
C = []
for ref in (lelac, game):
    v = E[[pos[i] for i in ref if i in pos]].mean(0); C.append(v / np.linalg.norm(v))
C = np.stack(C)
sim = E @ C.T
out = {str(i): [round(float(sim[pos[i], 0]), 3), round(float(sim[pos[i], 1]), 3)] for i in idx}
json.dump(out, open(f"{w}/voice_sim.json", "w"))
d = sim[:, 0] - sim[:, 1]
print("segments", len(idx), "lelac-leaning share", float((d > 0).mean()))
for name, ref in (("lelac refs", lelac), ("game refs", game)):
    print(name, np.round(np.percentile(d[[pos[i] for i in ref if i in pos]], [5, 50, 95]), 3))
