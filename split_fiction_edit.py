#!/usr/bin/env python3
"""Split Fiction editor (co-op, split-screen): long-form YouTube edit + vertical Shorts.

Forked from stream_edit.py (South Park) so each game can be tuned separately.
Two people on the facecam: Lelac (streamer) and Andrew, told apart by voice pitch
(work/<base>/f0.npy from pitch.py). Game dialogue = white subtitle text bottom-center.

Input: Raw/<name>.mp4 (game full-screen, facecam baked in top-right).
Needs work/<base>/transcript.json (Whisper small.en, word timestamps) and
work/<base>/scan.json (2 fps: in-game-subtitle fraction, motion, brightness).
Per-video edit decisions (effects, shorts, caption overrides) live in
work/<base>/plan.json so the same script can be reused for every episode.

Run (macOS):    .venv/bin/python -u split_fiction_edit.py "<base>" [main|shorts|docs|all]
Run (Windows):  .venv/Scripts/python.exe -u split_fiction_edit.py "<base>" [main|shorts|docs|all]   (Git Bash)
"""
import json, re, subprocess, sys
import numpy as np
from pathlib import Path

from pipeline_env import FFMPEG, ass_path, video_args

ROOT = Path(__file__).resolve().parent
FPS = 60
CAM = (1550, 0, 370, 268)                    # facecam x, y, w, h in source
GAME_ZOOM = {"C": (40, 230, 1422, 800),      # 1.35x punch-in (cutscenes / full screen)
             "L": (30, 287, 900, 506),       # ~2.1x into left player's half
             "R": (990, 287, 900, 506)}      # ~2.1x into right player's half (below facecam)
SHORT_CROP = {"C": (519, 75, 882, 930), "L": (12, 0, 935, 985),       # L: above the subtitle strip
              "R": (1055, 270, 769, 810)}                               # R: below the facecam
SUB_MIN = 0.005                              # white-subtitle fraction that counts as game dialogue
PITCH_SPLIT = 185.0                          # Hz: above = Lelac, below = Andrew
NAMES = {"lelac": "LELAC", "andrew": "ANDREW", "game": "GAME"}
GAP_MIN = 6.0                                # silences longer than this are dead air
GAP_KEEP = 1.2                               # keep this much on each side of a cut
AUDIO_GAIN_DB = 3.4                          # measured: source -17.4 LUFS -> ~-14
SFX_VOL = {"whoosh": 0.35, "boom": 0.55, "pop": 0.45, "ding": 0.35}

FIXES = {"Leela": "Lelac"}                    # extended per episode via plan["fixes"]


# Profanity (Shorts only, the user's choice): bleep in the audio and starred captions. The long video stays uncensored.
# Same word list as the South Park script.
from stream_edit import censor, find_bleeps
BLEEPS = []                                   # [(start, end)] raw-stream seconds, set in main()


def fix(t):
    for a, b in FIXES.items():
        t = t.replace(a, b)
    return t


def bleep_audio(offset, dur):
    """(filter prefix for the stream audio, extra amix chain, label) for bleeps inside [offset, offset+dur]."""
    r = [(max(0, a - offset), min(dur, b - offset)) for a, b in BLEEPS if b > offset and a < offset + dur]
    if not r:
        return "", [], []
    ex = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in r)
    mute = f"asetnsamples=n=240:p=0,volume=0:enable='{ex}',"
    tone = (f"sine=frequency=1000:sample_rate=48000:duration={dur:.3f},aformat=channel_layouts=stereo,"
            f"asetnsamples=n=240:p=0,volume=0.22,volume=0:enable='not({ex})'[bleep]")
    return mute, [tone], ["[bleep]"]


def snap(t):
    return round(t * FPS) / FPS


def ts(s, ms=False):
    h, m, sec = int(s // 3600), int(s % 3600 // 60), s % 60
    if ms:
        return f"{h}:{m:02d}:{sec:05.2f}"
    return f"{h}:{m:02d}:{int(sec):02d}" if h else f"{m}:{int(sec):02d}"


def load(base):
    w = ROOT / "work" / base
    tr = json.load(open(w / "transcript.json", encoding="utf-8"))
    scan = json.load(open(w / "scan.json", encoding="utf-8"))
    plan = json.load(open(w / "plan.json", encoding="utf-8"))
    FIXES.update(plan.get("fixes", {}))
    return w, tr, scan, plan


def voice(f0, a, b):
    v = f0[int(a * 100):max(int(a * 100) + 1, int(b * 100))]
    v = v[(v > 70) & (v < 400)]
    return float(np.median(v)) if len(v) >= 3 else None


def classify(tr, scan, plan, f0, vp=None):
    """Segments with speaker 'lelac', 'andrew' or 'game', labelled per word.
    voice_prob.json (diarize.py: ECAPA voice embeddings taught by the facecam + cutscenes) gives
    [p_lelac, p_andrew, p_game] per word; on-screen subtitles tilt toward 'game'. Falls back to
    subtitles + pitch if voice_prob.json is missing. plan force_*/drop/split override per segment."""
    vp = vp or {}
    force = {k: set(plan.get(f"force_{k}", [])) for k in ("lelac", "andrew", "game")}
    drop = set(plan["drop"])
    not_game = set(plan.get("not_game", []))   # streamer talking over subtitles: voice picks Lelac/Andrew
    split_hz = plan.get("pitch_split", PITCH_SPLIT)
    def subs_at(t0, t1):
        sl = scan[int(t0 * 2):max(int(t0 * 2) + 1, int(t1 * 2) + 1)]
        return sum(1 for x in sl if x[0] > SUB_MIN) / max(1, len(sl))
    out = []
    for i, s in enumerate(tr["segments"]):
        if not s["text"].strip() or i in drop:
            continue
        words = [w for w in s["words"] if w["word"].strip()]
        forced = next((k for k in force if i in force[k]), None)
        if forced:
            out.append({"i": i, "who": forced, "words": words}); continue
        cut = plan["split"].get(str(i))       # manual: speech before word index is streamer, rest is game
        labs = []
        for j, w in enumerate(words):
            p = vp.get(str(i), {}).get(str(j))
            sub = subs_at(w["start"], w["end"]) > 0
            if isinstance(p, list):
                pl, pa, pg = p
                pg *= 0 if i in not_game else (1.6 if sub else 0.5)
                lab = ("lelac", "andrew", "game")[int(np.argmax([pl, pa, pg]))]
            elif subs_at(s["start"], s["end"]) > 0.5:
                lab = "game"
            else:
                hz = voice(f0, w["start"], w["end"]) or voice(f0, s["start"], s["end"])
                lab = "lelac" if (hz or split_hz + 1) > split_hz else "andrew"
            if cut is not None:
                lab = "game" if j >= cut else (lab if lab != "game" else "lelac")
            labs.append(lab)
        for k in range(1, len(labs) - 1):      # smooth single-word flips
            if labs[k - 1] == labs[k + 1] != labs[k]: labs[k] = labs[k - 1]
        if len(labs) >= 2 and labs[0] != labs[1]: labs[0] = labs[1]
        if len(labs) >= 2 and labs[-1] != labs[-2]: labs[-1] = labs[-2]
        for w, l in zip(words, labs):
            if out and out[-1]["i"] == i and out[-1]["who"] == l: out[-1]["words"].append(w)
            else: out.append({"i": i, "who": l, "words": [w]})
    for o in out:
        o["text"] = fix("".join(w["word"] for w in o["words"]).strip())
        o["start"], o["end"] = o["words"][0]["start"], o["words"][-1]["end"]
    return [o for o in out if o["words"]]


def resolve_sides(plan, scan):
    """side 'auto' (default for zooms/shorts in gameplay) -> the half with more motion (scan cols 3/4)."""
    def pick(t0, t1):
        sl = scan[int(t0 * 2):max(int(t0 * 2) + 1, int(t1 * 2))]
        l, r = sum(x[3] for x in sl), sum(x[4] for x in sl)
        return "L" if l >= r else "R"
    for e in plan["effects"]:
        if e["kind"] == "zoom" and e.get("side", "auto") == "auto": e["side"] = pick(e["t"], e["t"] + e["dur"])
    for sh in plan["shorts"]:
        if sh.get("side", "auto") == "auto": sh["side"] = pick(sh["start"], sh["end"])


def keep_ranges(tr, scan, plan, dur):
    iv = [(w["start"], w["end"]) for s in tr["segments"] if s["text"].strip() for w in s["words"]]
    iv += [(i / 2, i / 2 + 0.5) for i, x in enumerate(scan) if x[0] > SUB_MIN]
    iv += [(e["t"], e["t"] + e.get("dur", 2)) for e in plan["effects"]]   # never cut an effect
    iv += [tuple(r) for r in plan.get("protect", [])]                     # ranges kept whole (e.g. intro)
    iv.sort()
    merged = []
    for a, b in iv:
        if merged and a <= merged[-1][1] + 0.3:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    start, end = plan["trim_start"], plan["trim_end"]
    keeps, seg0, cur = [], start, start
    for a, b in merged:
        if a - cur > GAP_MIN and a > start:
            keeps.append((seg0, cur + GAP_KEEP))
            seg0 = a - GAP_KEEP
        cur = max(cur, b)
    keeps.append((seg0, end))
    keeps = [(snap(max(a, start)), snap(min(b, end))) for a, b in keeps if min(b, end) > max(a, start)]
    out = []
    for a, b in keeps:                         # merge touching ranges
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def src_to_edit(keeps):
    def f(t):
        acc = 0.0
        for a, b in keeps:
            if t < a:
                return acc
            if t <= b:
                return acc + t - a
            acc += b - a
        return acc
    return f


# ---------- ASS ----------
ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{styles}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def chunks(words, max_chars, max_gap=0.6):
    """Group words into short caption chunks."""
    out, cur = [], []
    for w in words:
        t = w["word"].strip()
        if cur and (len(" ".join(x["word"].strip() for x in cur + [w])) > max_chars
                    or w["start"] - cur[-1]["end"] > max_gap):
            out.append(cur); cur = []
        cur.append(w)
        if t[-1:] in ".?!" and len(cur) > 1:
            out.append(cur); cur = []
    if cur: out.append(cur)
    res = []
    for c in out:
        res.append({"start": c[0]["start"], "end": max(c[-1]["end"], c[0]["start"] + 0.6),
                    "text": fix(" ".join(x["word"].strip() for x in c))})
    for a, b in zip(res, res[1:]):           # hold until next chunk if close, no overlap
        if b["start"] - a["end"] < 0.4: a["end"] = b["start"]
        a["end"] = min(a["end"], b["start"])
    return res


def esc(t):
    return t.replace("{", "(").replace("}", ")")


def main_ass(segs, plan, path):
    styles = "\n".join([
        "Style: Cap,Arial,34,&H00FFFFFF,&H00FFFFFF,&H70000000,&H70000000,1,0,0,0,100,100,0,0,3,6,0,8,10,10,10,1",
        "Style: CapA,Arial,34,&H00FFD27A,&H00FFFFFF,&H70000000,&H70000000,1,0,0,0,100,100,0,0,3,6,0,8,10,10,10,1",
        "Style: Pop,Impact,110,&H0000E5FF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,1,0,1,8,4,5,10,10,10,1",
        "Style: Title,Arial Black,44,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,0,0,1,4,2,1,60,60,60,1",
    ])
    ev = []
    cam_pops = [(e["t"], e["t"] + e["dur"]) for e in plan["effects"] if e["kind"] == "cam"]
    for s in segs:
        if s["who"] == "game": continue
        for c in chunks(s["words"], 20):
            under_big_cam = any(a - 0.05 <= c["start"] < b for a, b in cam_pops)
            pos = r"{\pos(1544,566)}" if under_big_cam else r"{\pos(1735,280)}"
            st = "Cap" if s["who"] == "lelac" else "CapA"
            ev.append(f"Dialogue: 0,{ts(c['start'],1)},{ts(c['end'],1)},{st},,0,0,0,,{pos}{esc(c['text'])}")
    for e in plan["effects"]:
        if not e.get("text"): continue
        t0, t1 = e["t"], e["t"] + e["dur"]
        if e["kind"] == "title":
            ev.append(f"Dialogue: 1,{ts(t0,1)},{ts(t1,1)},Title,,0,0,0,,"
                      r"{\fad(300,400)\move(-400,1010,60,1010,0,350)\an1}" + esc(e["text"]))
        else:
            x, y = e.get("pos", (640, 520))
            ev.append(f"Dialogue: 2,{ts(t0,1)},{ts(t1,1)},Pop,,0,0,0,,"
                      rf"{{\pos({x},{y})\frz{e.get('rot', -6)}\fscx160\fscy160\t(0,140,\fscx100\fscy100)\fad(0,250)}}"
                      + esc(e["text"]))
    path.write_text(encoding="utf-8", data=ASS_HEAD.format(w=1920, h=1080, styles=styles) + "\n".join(ev) + "\n")


def enable_expr(ranges):
    return "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in ranges) or "0"


def select_expr(keeps):
    return "+".join(f"gte(t,{a:.4f})*lt(t,{b:.4f})" for a, b in keeps)


def envelope_expr(keeps, fade=0.012):
    # per-cut micro fades so jump cuts don't click
    terms = [f"between(t,{a:.4f},{b:.4f})*min(1,min((t-{a:.4f})/{fade},({b:.4f}-t)/{fade}))" for a, b in keeps]
    return "+".join(terms)


def audio_input(plan, sargs, a=None, b=None):
    """plan["audio_src"]: replacement audio (e.g. game_boost.py output, same timeline as the raw).
    Returns extra ffmpeg input args and the input index to read audio from (0 = the raw video)."""
    if not plan.get("audio_src"):
        return [], 0
    seek = ["-ss", f"{a:.3f}", "-to", f"{b:.3f}"] if a is not None else []
    return seek + ["-i", str(ROOT / plan["audio_src"])], 1 + sargs.count("-i")


def sfx_inputs(events, t_offset=0.0):
    """Build ffmpeg -i args + filter chains for SFX events (times relative to the cut input)."""
    args, chains, labels = [], [], []
    for k, (name, t) in enumerate(events):
        args += ["-i", str(ROOT / "SFX" / f"{name}.wav")]
        ms = max(0, int((t - t_offset) * 1000))
        lab = f"sfx{k}"
        chains.append(f"[{k+1}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                      f"volume={SFX_VOL[name]},adelay={ms}|{ms}[{lab}]")
        labels.append(f"[{lab}]")
    return args, chains, labels


def render_main(name, w, src, segs, keeps, plan):
    out_dir = ROOT / "Ouput" / name; out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name} - YouTube Edit.mp4"
    ass = w / "main.ass"
    main_ass(segs, plan, ass)
    cam = [(e["t"], e["t"] + e["dur"]) for e in plan["effects"] if e["kind"] == "cam"]
    zooms = {k: [(e["t"], e["t"] + e["dur"]) for e in plan["effects"] if e["kind"] == "zoom" and e.get("side", "C") == k]
             for k in GAME_ZOOM}
    zoom = [r for v in zooms.values() for r in v]
    sfx = [(e["sfx"], e["t"]) for e in plan["effects"] if e.get("sfx")]
    sfx += [("whoosh", e["t"] - 0.15) for e in plan["effects"] if e["kind"] in ("cam", "zoom") and not e.get("sfx")]
    sargs, schains, slabels = sfx_inputs(sfx)
    logos = [e for e in plan["effects"] if e["kind"] == "logo"]   # PNG intro (e.g. game logo), fades in/out
    lchains, lin = [], len(sargs) // 2 + 1
    for k, e in enumerate(logos):
        sargs += ["-loop", "1", "-t", f"{e['dur']:.3f}", "-i", str(ROOT / e["file"])]
        lchains.append(f"[{lin + k}:v]format=rgba,fade=t=in:st=0:d=0.5:alpha=1,"
                       f"fade=t=out:st={e['dur'] - 0.6:.3f}:d=0.6:alpha=1,setpts=PTS+{e['t']:.3f}/TB[logo{k}]")
    ain, aidx = audio_input(plan, sargs)
    sargs += ain
    cx, cy, cw, ch = CAM
    sel = select_expr(keeps)
    (w / "select.txt").write_text(encoding="utf-8", data=sel)
    vf = [
        f"[0:v]split=6[base][c][c2][gC][gL][gR]",
        f"[c]crop={cw}:{ch}:{cx}:{cy},scale={cw*2}:{ch*2},pad={cw*2+12}:{ch*2+12}:6:6:white[cambig]",
        f"[c2]crop={cw}:{ch}:{cx}:{cy}[camsmall]",
        *[f"[g{k}]crop={g[2]}:{g[3]}:{g[0]}:{g[1]},scale=1920:1080[gz{k}]" for k, g in GAME_ZOOM.items()],
        f"[base][gzC]overlay=enable='{enable_expr(zooms['C'])}'[z1]",
        f"[z1][gzL]overlay=enable='{enable_expr(zooms['L'])}'[z2]",
        f"[z2][gzR]overlay=enable='{enable_expr(zooms['R'])}'[v1]",
        f"[v1][camsmall]overlay={cx}:{cy}:enable='{enable_expr(zoom)}'[v2]",
        f"[v2][cambig]overlay=W-w:0:enable='{enable_expr(cam)}'[v3l0]",
        *lchains,
        *[f"[v3l{k}][logo{k}]overlay=(W-w)/2:(H-h)/2-70:eof_action=pass[v3l{k + 1}]" for k in range(len(logos))],
        f"[v3l{len(logos)}]ass='{ass_path(ass)}'[v4]",
        f"[v4]select='{sel}',setpts=N/FRAME_RATE/TB[vout]",
    ]
    mute, bchain, blab = "", [], []            # long video is not bleeped (Shorts only)
    af = schains + bchain + [
        f"[{aidx}:a]{mute}volume={plan.get('main_audio_gain_db', plan.get('audio_gain_db', AUDIO_GAIN_DB))}dB[ma]",
        f"[ma]{''.join(slabels + blab)}amix=inputs={len(slabels)+len(blab)+1}:normalize=0:duration=first[mix]",
        f"[mix]alimiter=limit=0.84:attack=5:release=60:level=disabled,asetnsamples=n=48:p=0,"
        f"volume='{envelope_expr(keeps)}':eval=frame,asetnsamples=n=800:p=0,"
        f"aselect='{sel}',asetpts=N/SR/TB[aout]",
    ]
    graph = ";\n".join(vf + af)
    (w / "main_graph.txt").write_text(encoding="utf-8", data=graph)
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-stats", "-i", str(src)] + sargs + [
        "-filter_complex_script", str(w / "main_graph.txt"), "-map", "[vout]", "-map", "[aout]",
        *video_args("16M", "24M", "32M"), "-r", str(FPS), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", str(out)]
    print("rendering main ->", out.name)
    subprocess.run(cmd, check=True)
    return out


# ---------- Shorts ----------
def short_ass(segs, a, b, sh, path):
    styles = "\n".join([
        "Style: Me,Arial Black,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,6,2,8,60,60,10,1",
        "Style: Andrew,Arial Black,62,&H00FFD27A,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,6,2,8,60,60,10,1",
        "Style: Game,Arial Black,56,&H0000E5FF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,6,2,8,60,60,10,1",
        "Style: Hook,Arial Black,58,&H00000000,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,3,18,0,5,60,60,10,1",
    ])
    ev = []
    for s in segs:
        if s["end"] < a or s["start"] > b: continue
        ws = [x for x in s["words"] if a <= x["start"] < b]
        me = s["who"] != "game"
        st = {"lelac": "Me", "andrew": "Andrew", "game": "Game"}[s["who"]]
        for c in chunks(ws, 22 if me else 30):
            ev.append(f"Dialogue: 0,{ts(c['start']-a,1)},{ts(min(c['end'],b)-a,1)},"
                      f"{st},,0,0,0,,{{\\pos(540,830)}}{esc(censor(c['text']).upper() if me else censor(c['text']))}")
    ev.append(f"Dialogue: 1,{ts(0,1)},{ts(3.2,1)},Hook,,0,0,0,,{{\\pos(540,690)\\fscx120\\fscy120\\t(0,150,\\fscx100\\fscy100)}}{esc(sh['hook'])}")
    path.write_text(encoding="utf-8", data=ASS_HEAD.format(w=1080, h=1920, styles=styles) + "\n".join(ev) + "\n")


def render_short(name, w, src, segs, keeps, sh, n, plan):
    a, b = sh["start"], sh["end"]
    local = [(max(x, a) - a, min(y, b) - a) for x, y in keeps if y > a and x < b]
    local = [(snap(x), snap(y)) for x, y in local]
    ass = w / f"short{n}.ass"
    short_ass(segs, a, b, sh, ass)
    cx, cy, cw, ch = CAM
    sel = select_expr(local)
    sfx = [(name, t - a) for name, t in sh.get("sfx", [])] + [("whoosh", 0.0)]
    sargs, schains, slabels = sfx_inputs(sfx)
    ain, aidx = audio_input(plan, sargs, a, b)
    sargs += ain
    mute, bchain, blab = bleep_audio(a, b - a)
    graph = ";\n".join([
        "[0:v]split=2[c][g]",
        f"[c]crop={cw}:{ch}:{cx}:{cy},scale=1080:782[top]",
        "[g]crop={2}:{3}:{0}:{1},scale=1080:1138[bot]".format(*SHORT_CROP[sh.get("side", "C")]),
        "[top][bot]vstack[st]",
        f"[st]ass='{ass_path(ass)}'[s1]",
        f"[s1]select='{sel}',setpts=N/FRAME_RATE/TB[vout]",
    ] + schains + bchain + [
        f"[{aidx}:a]{mute}volume={plan.get('audio_gain_db', AUDIO_GAIN_DB)}dB[ma]",
        f"[ma]{''.join(slabels + blab)}amix=inputs={len(slabels)+len(blab)+1}:normalize=0:duration=first[mix]",
        f"[mix]alimiter=limit=0.84:attack=5:release=60:level=disabled,asetnsamples=n=48:p=0,"
        f"volume='{envelope_expr(local)}':eval=frame,asetnsamples=n=800:p=0,"
        f"aselect='{sel}',asetpts=N/SR/TB[aout]",
    ])
    gpath = w / f"short{n}_graph.txt"
    gpath.write_text(encoding="utf-8", data=graph)
    out_dir = ROOT / "Ouput" / name / "Shorts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name} - Short {n} - {sh['name']}.mp4"
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
           "-i", str(src)] + sargs + [
        "-filter_complex_script", str(gpath), "-map", "[vout]", "-map", "[aout]",
        *video_args("12M"), "-r", str(FPS), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out)]
    print(f"rendering short {n} ({sum(y-x for x,y in local):.1f}s) ->", out.name)
    subprocess.run(cmd, check=True)


# ---------- Docs ----------
def write_docs(name, segs, keeps, plan, tr):
    f = src_to_edit(keeps)
    segs = [s for s in segs if plan["trim_start"] <= s["start"] < plan["trim_end"]]   # pre-roll chat is cut
    out_dir = ROOT / "Ouput" / name; out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"{plan['title_options'][0]}", "Full transcript (timestamps match the edited YouTube video).",
             "LELAC = streamer, ANDREW = co-op partner, GAME = in-game dialogue. Raw-stream times in [brackets].", ""]
    for s in segs:
        lines.append(f"{ts(f(s['start']))}  [{ts(s['start'])}]  {NAMES[s['who']]:<6}: {s['text']}")
    (out_dir / f"{name} - Transcript.txt").write_text(encoding="utf-8", data="\n".join(lines) + "\n")

    # SRT of everything (upload as YouTube closed captions for accessibility + SEO)
    srt, k = [], 1
    def st(x): return f"{int(x//3600):02d}:{int(x%3600//60):02d}:{int(x%60):02d},{int(round(x%1*1000))%1000:03d}"
    for s in segs:
        for c in chunks(s["words"], 42):
            a, b = f(c["start"]), f(c["end"])
            if b - a < 0.2: continue
            pre = {"lelac": "", "andrew": "[Andrew] ", "game": "[Game] "}[s["who"]]
            srt.append(f"{k}\n{st(a)} --> {st(b)}\n{pre}{c['text']}\n"); k += 1
    (out_dir / f"{name} - Captions.srt").write_text(encoding="utf-8", data="\n".join(srt))

    ch = "\n".join(f"{ts(f(t)) if f(t) > 0 else '0:00'} {name}" for t, name in plan["chapters"])
    total = sum(b - a for a, b in keeps)
    meta = [f"FINAL LENGTH: {ts(total)}  (raw stream {ts(plan['raw_dur'])}, {ts(plan['raw_dur']-total)} of dead air removed)", "",
            "TITLE OPTIONS", *[f"  {i+1}. {t}" for i, t in enumerate(plan["title_options"])], "",
            "DESCRIPTION (paste as-is)", "-" * 40, plan["description"].replace("{CHAPTERS}", ch), "-" * 40, "",
            "TAGS (comma-separated, paste into YouTube tags box)", ", ".join(plan["tags"]), "",
            "SHORTS", *[f"  Short {i+1}: {s['name']}\n     Title: {s['title']}\n     Raw-stream source: {ts(s['start'])}-{ts(s['end'])}"
                       for i, s in enumerate(plan["shorts"])], "",
            "THUMBNAIL IDEAS", re.sub(r"\{T:([\d.]+)\}", lambda m: f"{ts(f(float(m[1])))} [{ts(float(m[1]))}]",
                                      plan["thumbnails"].strip()), ""]
    (out_dir / f"{name} - YouTube Upload Kit.txt").write_text(encoding="utf-8", data="\n".join(meta))
    print("docs written; final length", ts(total))


def main():
    base = sys.argv[1]
    what = sys.argv[2] if len(sys.argv) > 2 else "all"
    w, tr, scan, plan = load(base)
    src = ROOT / "Raw" / f"{plan['raw']}"
    if not src.exists():                          # finished episodes get moved to Raw Archive/
        src = ROOT / "Raw Archive" / f"{plan['raw']}"
    global BLEEPS
    BLEEPS = [] if plan.get("no_bleep") else find_bleeps(tr)
    print(f"{len(BLEEPS)} bleeps")
    name = Path(plan["raw"]).stem
    vp = json.load(open(w / "voice_prob.json", encoding="utf-8")) if (w / "voice_prob.json").exists() else {}
    segs = classify(tr, scan, plan, np.load(w / "f0.npy"), vp)
    resolve_sides(plan, scan)
    keeps = keep_ranges(tr, scan, plan, plan["raw_dur"])
    json.dump(keeps, open(w / "keeps.json", "w", encoding="utf-8"))
    print(f"{len(keeps)} keep ranges, {sum(b-a for a,b in keeps)/60:.1f} min kept")
    if what in ("docs", "all"): write_docs(name, segs, keeps, plan, tr)
    if what in ("shorts", "all"):
        only = [int(x) for x in sys.argv[3:]] or range(1, len(plan["shorts"]) + 1)
        for n in only: render_short(name, w, src, segs, keeps, plan["shorts"][n - 1], n, plan)
    if what in ("main", "all"): render_main(name, w, src, segs, keeps, plan)


if __name__ == "__main__":
    main()
