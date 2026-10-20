# Three-way speaker ID per word: Lelac / Andrew / game characters.
# SpeechBrain ECAPA embeddings on 1.5 s windows (hop 0.5 s) over ALL speech.
# Output voice_prob.json {seg_idx: {word_idx: [p_lelac, p_andrew, p_game]}}. Run with .venv-voice/bin/python.
import json, wave, numpy as np, torch, sys, os
w = sys.argv[1] if len(sys.argv) > 1 else "work/sf1"
SUB_MIN = 0.005
x = np.frombuffer(wave.open(f"{w}/audio16k.wav").readframes(10**9), np.int16).astype(np.float32) / 32768
tr = json.load(open(f"{w}/transcript.json")); scan = json.load(open(f"{w}/scan.json"))
subs = np.array([q[0] for q in scan])
segs = []
for i, s in enumerate(tr["segments"]):
    ws = [q for q in s["words"] if q["word"].strip()]
    if ws: segs.append((i, ws))
wins = []
for i, ws in segs:
    a, b = ws[0]["start"], ws[-1]["end"]; t = a
    while True:
        c = (t + min(t + 1.5, b)) / 2
        wins.append((i, max(0, c - 0.75), c + 0.75, c))
        if t + 1.5 >= b: break
        t += 0.5
if os.path.exists(f"{w}/ecapa_all.npy") and len(np.load(f"{w}/ecapa_all.npy")) == len(wins):
    E = np.load(f"{w}/ecapa_all.npy")
else:
    from speechbrain.inference.speaker import EncoderClassifier
    enc = EncoderClassifier.from_hparams("speechbrain/spkrec-ecapa-voxceleb", savedir="pretrained/ecapa", run_opts={"device": "cpu"})
    E = []
    for k in range(0, len(wins), 64):
        batch = [torch.tensor(x[int(a * 16000):int(b * 16000)]) for _, a, b, _ in wins[k:k + 64]]
        L = max(len(q) for q in batch)
        wav = torch.stack([torch.nn.functional.pad(q, (0, L - len(q))) for q in batch])
        with torch.no_grad(): E.append(enc.encode_batch(wav, torch.tensor([len(q) / L for q in batch])).squeeze(1).numpy())
    E = np.concatenate(E); E /= np.linalg.norm(E, axis=1, keepdims=True)
    np.save(f"{w}/ecapa_all.npy", E)
print("windows", len(E))
# Speakers: spherical 2-means on windows with no on-screen subtitles (= only Lelac/Andrew talking);
# the higher-pitched cluster is Lelac. (Facecam mouth motion was tried as a teacher and was unreliable:
# Lelac's face moves a lot even while listening.)
f0 = np.load(f"{w}/f0.npy")
def pitch(a, b):
    v = f0[int(a * 100):int(b * 100)]; v = v[(v > 70) & (v < 400)]; return np.median(v) if len(v) else np.nan
nosub = np.array([not (subs[int(a * 2):int(b * 2) + 1] > SUB_MIN).any() for _, a, b, _ in wins])
allsub = np.array([len(subs[int(a * 2):int(b * 2) + 1]) > 0 and (subs[int(a * 2):int(b * 2) + 1] > SUB_MIN).all() for _, a, b, _ in wins])
S = E[nosub]
c0 = S[0]; c1 = S[np.argmin(S @ c0)]; c0 = S[np.argmin(S @ c1)]; C = np.stack([c0, c1])
for _ in range(60):
    lab = (S @ C.T).argmax(1)
    C = np.stack([S[lab == k].mean(0) for k in (0, 1)]); C /= np.linalg.norm(C, axis=1, keepdims=True)
hz = np.array([pitch(a, b) for _, a, b, _ in wins])[nosub]
med = [np.nanmedian(hz[lab == k]) for k in (0, 1)]
if med[0] < med[1]: C = C[::-1]
print("cluster pitch lelac/andrew", sorted(med, reverse=True), "lelac share", float(((S @ C.T).argmax(1) == 0).mean()))
sim = E @ C.T                                   # [n, 2] similarity to Lelac, Andrew
best = sim.max(1)
# game voices: low similarity to both of us. Calibrate on fully-subtitled windows vs subtitle-free windows.
g, h = best[allsub], best[nosub]
tau = float(np.percentile(h, 10))
print("best-sim nosub p10/p50", np.percentile(h, [10, 50]).round(3), "allsub p50/p90", np.percentile(g, [50, 90]).round(3) if len(g) else None, "tau", round(tau, 3))
p_sp = 1 / (1 + np.exp(-(sim[:, 0] - sim[:, 1]) * 15))
p_game = 1 / (1 + np.exp(-(tau - best) * 25))
P = np.stack([p_sp * (1 - p_game), (1 - p_sp) * (1 - p_game), p_game], 1)
print("share lelac/andrew/game", np.bincount(P.argmax(1), minlength=3) / len(P))
bywin = {}
for (i, a, b, c), p in zip(wins, P): bywin.setdefault(i, []).append((c, p))
out = {}
for i, ws in segs:
    cs = np.array([c for c, _ in bywin[i]]); ps = np.array([p for _, p in bywin[i]])
    d = {}
    for j, q in enumerate(ws):
        mid = (q["start"] + q["end"]) / 2
        wt_ = np.exp(-((cs - mid) / 0.5) ** 2) + 1e-6
        d[str(j)] = [round(float(v), 3) for v in (wt_[:, None] * ps).sum(0) / wt_.sum()]
    out[str(i)] = d
json.dump(out, open(f"{w}/voice_prob.json", "w"))
