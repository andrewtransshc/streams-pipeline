# Per-person mouth activity from the facecam at 10 fps -> mouth.npy [N,2] (Lelac=left face, Andrew=right face).
# YuNet (OpenCV) face + mouth-corner landmarks; ROI around the mouth normalized to 40x24;
# activity = mean abs change vs the previous frame's ROI (landmark-aligned, so head motion mostly cancels). NaN = no face.
import subprocess, numpy as np, cv2, sys
src, outp = sys.argv[1], sys.argv[2]
W, H = 740, 536
det = cv2.FaceDetectorYN.create("pretrained/face_detection_yunet_2023mar.onnx", "", (W, H), 0.6)
p = subprocess.Popen(["bin/ffmpeg", "-v", "error", "-i", src, "-vf",
     f"fps=10,crop=370:268:1550:0,scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
prev = [None, None]; out = []
while True:
    b = p.stdout.read(W * H * 3)
    if len(b) < W * H * 3: break
    img = np.frombuffer(b, np.uint8).reshape(H, W, 3)
    _, faces = det.detect(img)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    slot = [None, None]
    for f in (faces if faces is not None else []):
        s = 0 if f[0] + f[2] / 2 < W * 0.55 else 1
        if slot[s] is None or f[14] > slot[s][14]: slot[s] = f
    row = []
    for s in (0, 1):
        f = slot[s]
        if f is None: row.append(np.nan); prev[s] = None; continue
        mx, my = (f[10] + f[12]) / 2, (f[11] + f[13]) / 2
        d = max(12.0, float(np.hypot(f[10] - f[12], f[11] - f[13])))
        x0, x1 = int(mx - d * 0.9), int(mx + d * 0.9); y0, y1 = int(my - d * 0.45), int(my + d * 0.75)
        roi = g[max(0, y0):max(1, y1), max(0, x0):max(1, x1)]
        if roi.size < 50: row.append(np.nan); prev[s] = None; continue
        roi = cv2.resize(roi, (40, 24)).astype(np.float32); roi = (roi - roi.mean()) / (roi.std() + 1)
        row.append(np.nan if prev[s] is None else float(np.abs(roi - prev[s]).mean()))
        prev[s] = roi
    out.append(row)
np.save(outp, np.array(out, np.float32)); print(len(out))
