# Speaker ID for Lelac vs Andrew without extra installs:
# per-word MFCC (timbre) + pitch features; train logistic regression on confidently-pitched words,
# predict every streamer word -> voice_prob.json {seg_idx: [p_lelac per word]}.
import json, wave, numpy as np, torch, sys
sys.path.insert(0, "."); import split_fiction_edit as E
w = "work/sf1"
x = np.frombuffer(wave.open(f"{w}/audio16k.wav").readframes(10**9), np.int16).astype(np.float32) / 32768
f0 = np.load(f"{w}/f0.npy"); tr = json.load(open(f"{w}/transcript.json")); scan = json.load(open(f"{w}/scan.json"))
SR, N, HOP, NM = 16000, 400, 160, 40
mel = lambda f: 2595 * np.log10(1 + f / 700); imel = lambda m: 700 * (10 ** (m / 2595) - 1)
pts = imel(np.linspace(mel(60), mel(7600), NM + 2)); bins = np.floor((N + 1) * pts / SR).astype(int)
fb = np.zeros((NM, N // 2 + 1))
for m in range(1, NM + 1):
    a, c, b = bins[m - 1], bins[m], bins[m + 1]
    fb[m - 1, a:c] = (np.arange(a, c) - a) / max(1, c - a); fb[m - 1, c:b] = (b - np.arange(c, b)) / max(1, b - c)
dct = np.cos(np.pi / NM * (np.arange(NM)[:, None] + 0.5) * np.arange(1, 21)[None, :])
def feats(a, b):
    s, e = int(a * SR), int(b * SR)
    if e - s < N * 2: return None
    seg = x[s:e]; nf = (len(seg) - N) // HOP
    fr = seg[np.arange(nf)[:, None] * HOP + np.arange(N)] * np.hamming(N)
    p = np.abs(np.fft.rfft(fr, N)) ** 2
    en = p.sum(1); keep = en > np.percentile(en, 40)        # voiced/loud frames only
    if keep.sum() < 3: return None
    mf = np.log(p[keep] @ fb.T + 1e-10) @ dct
    hz = E.voice(f0, a, b)
    return np.concatenate([mf.mean(0), mf.std(0), [np.log(hz) if hz else 0, 1 if hz else 0]])
X, idx = [], []
for i, s in enumerate(tr["segments"]):
    a2, b2 = int(s["start"] * 2), max(int(s["start"] * 2) + 1, int(s["end"] * 2) + 1)
    if sum(1 for q in scan[a2:b2] if q[0] > E.SUB_MIN) / max(1, len(scan[a2:b2])) > 0.5: continue
    for j, wd in enumerate(x_ for x_ in s["words"] if x_["word"].strip()):
        v = feats(wd["start"] - 0.03, wd["end"] + 0.03)
        if v is not None: X.append(v); idx.append((i, j, E.voice(f0, wd["start"], wd["end"]) or 0))
X = np.array(X, np.float32); mu, sd = X.mean(0), X.std(0) + 1e-6; Xn = torch.tensor((X - mu) / sd)
hz = np.array([h for _, _, h in idx]); lab = np.full(len(idx), -1); lab[hz > 215] = 1; lab[(hz > 0) & (hz < 125)] = 0
print("train lelac", (lab == 1).sum(), "andrew", (lab == 0).sum(), "of", len(idx))
tm = lab >= 0; Xt = Xn[tm][:, :40]; yt = torch.tensor(lab[tm], dtype=torch.float32)   # timbre only (no pitch) to avoid circularity
model = torch.nn.Linear(40, 1); opt = torch.optim.Adam(model.parameters(), 0.01, weight_decay=1e-3)
pw = torch.tensor((yt == 0).sum() / max(1, (yt == 1).sum()))
for _ in range(600):
    opt.zero_grad(); l = torch.nn.functional.binary_cross_entropy_with_logits(model(Xt).squeeze(1), yt, pos_weight=pw); l.backward(); opt.step()
with torch.no_grad(): pr = torch.sigmoid(model(Xn[:, :40]).squeeze(1)).numpy()
print("train acc", float(((pr[tm] > 0.5) == (lab[tm] == 1)).mean()))
out = {}
for (i, j, h), p in zip(idx, pr):
    # combine timbre with pitch evidence
    if h: p = 0.5 * p + 0.5 * (1 / (1 + np.exp(-(h - 185) / 15)))
    out.setdefault(str(i), {})[str(j)] = round(float(p), 3)
json.dump(out, open(f"{w}/voice_prob.json", "w"))
allp = np.array([v for d in out.values() for v in d.values()]); print("words lelac", (allp > 0.5).mean())
