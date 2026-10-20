# Voice pitch track (F0, Hz) every 10 ms from audio16k.wav -> f0.npy (0 = unvoiced).
# Used to tell Lelac (higher voice) from Andrew (lower voice).
import numpy as np, wave, sys
w = sys.argv[1] if len(sys.argv) > 1 else "work/sf1"
x = np.frombuffer(wave.open(f"{w}/audio16k.wav").readframes(10**9), np.int16).astype(np.float32) / 32768
SR, HOP, N = 16000, 160, 800                     # 50 ms window
lo, hi = SR // 400, SR // 70                     # lags for 400..70 Hz
nf = (len(x) - N) // HOP
f0 = np.zeros(nf, np.float32)
for s in range(0, nf, 20000):
    idx = np.arange(s, min(nf, s + 20000))[:, None] * HOP + np.arange(N)
    fr = x[idx]; fr = fr - fr.mean(1, keepdims=True)
    energy = (fr ** 2).mean(1)
    F = np.fft.rfft(fr * np.hanning(N), 2 * N)
    ac = np.fft.irfft(np.abs(F) ** 2)[:, :hi + 1]
    ac = ac / np.maximum(ac[:, :1], 1e-9)
    seg = ac[:, lo:hi + 1]
    k = seg.argmax(1); peak = seg.max(1)
    hz = SR / (k + lo)
    f0[s:s + len(k)] = np.where((peak > 0.45) & (energy > 1e-5), hz, 0)
np.save(f"{w}/f0.npy", f0); print("frames", nf, "voiced", float((f0 > 0).mean()))
