# Raise game audio that the DJI mics picked up from the room, without changing Lelac/Andrew.
# Demucs splits the track into vocals + no_vocals (music/SFX/ambience).
#   no_vocals: + MUSIC_DB everywhere.
#   vocals: during game-dialogue spans (classify() 'game' words, ±0.15 s), quiet audio is lifted toward
#           TARGET_DB (max +DIALOG_MAX_DB); anything already at speaking level gets no lift, so a mislabeled
#           streamer line can't jump in volume.
# Usage: game_boost.py <vocals.wav> <no_vocals.wav> <t0 seconds into raw> <out.wav>
import json, sys, wave, numpy as np
sys.path.insert(0, "."); import split_fiction_edit as E
MUSIC_DB, DIALOG_MAX_DB, TARGET_DB = 10.0, 10.0, -21.0
voc_p, nov_p, t0, outp = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
def rd(p):
    f = wave.open(p); sr, n = f.getframerate(), f.getnchannels()
    return np.frombuffer(f.readframes(10**10), np.int16).reshape(-1, n).astype(np.float32) / 32768, sr
voc, sr = rd(voc_p); nov, _ = rd(nov_p)
w, tr, scan, plan = E.load("sf1")
vp = json.load(open(w / "voice_prob.json"))
segs = E.classify(tr, scan, plan, np.load(w / "f0.npy"), vp)
N = len(voc); hop = int(sr * 0.01); nf = N // hop + 1
game = np.zeros(nf, bool); me = np.zeros(nf, bool)
for s in segs:
    for wd in s["words"]:
        a, b = int((wd["start"] - t0 - 0.15) * 100), int((wd["end"] - t0 + 0.15) * 100)
        if b < 0 or a >= nf: continue
        (game if s["who"] == "game" else me)[max(0, a):min(nf, b)] = True
game &= ~me
mono = voc.mean(1); fr = np.pad(mono, (0, nf * hop - N))[:nf * hop].reshape(nf, hop)
lvl = 10 * np.log10(np.convolve((fr ** 2).mean(1), np.ones(10) / 10, "same") + 1e-10)   # 100 ms RMS, dBFS
g = np.where(game, np.clip(TARGET_DB - lvl, 0, DIALOG_MAX_DB), 0.0)
k = np.ones(15) / 15; g = np.convolve(g, k, "same")                                     # ~150 ms smoothing
gain = np.repeat(10 ** (g / 20), hop)[:N][:, None]
out = voc * gain + nov * 10 ** (MUSIC_DB / 20)
HEADROOM_DB = 10.0          # written 10 dB down so boosted peaks never clip; the editor's gain + limiter restore level
out *= 10 ** (-HEADROOM_DB / 20)
peak = np.abs(out).max(); print("peak before limiter", round(20 * np.log10(peak), 1), "dBFS; game frames", int(game.sum()))
o = wave.open(outp, "wb"); o.setnchannels(voc.shape[1]); o.setsampwidth(2); o.setframerate(sr)
o.writeframes((np.clip(out, -1, 1) * 32767).astype(np.int16).tobytes()); o.close()
