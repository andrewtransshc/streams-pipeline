# ECAPA embedding per transcript segment -> emb.npy + emb_idx.json (centroids chosen later in voiceid step)
import json, wave, numpy as np, torch
torch.set_num_threads(8)
w = "work/sp3"
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
order = np.argsort([len(c) for c in clips])          # batch similar lengths -> far less padding
E = np.zeros((len(clips), 192), np.float32)
for k in range(0, len(order), 32):
    ids = order[k:k + 32]; batch = [clips[j] for j in ids]; L = max(len(q) for q in batch)
    wav = torch.stack([torch.nn.functional.pad(q, (0, L - len(q))) for q in batch])
    with torch.no_grad(): e = enc.encode_batch(wav, torch.tensor([len(q) / L for q in batch])).squeeze(1).numpy()
    E[ids] = e
E /= np.linalg.norm(E, axis=1, keepdims=True)
np.save(f"{w}/emb.npy", E); json.dump(idx, open(f"{w}/emb_idx.json", "w")); print("done", len(idx))
