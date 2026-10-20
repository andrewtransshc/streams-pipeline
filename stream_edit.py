#!/usr/bin/env python3
"""Stream editor: long-form YouTube playthrough edit + vertical Shorts.

Input: Raw/<name>.mp4 (game full-screen, facecam baked in top-right).
Needs work/<base>/transcript.json (Whisper small.en, word timestamps) and
work/<base>/scan.json (2 fps: in-game-subtitle fraction, motion, brightness).
Per-video edit decisions (effects, shorts, caption overrides) live in
work/<base>/plan.json so the same script can be reused for every episode.

Run:  PATH="$PWD/bin:$PATH" .venv/bin/python -u stream_edit.py "<base>" [main|shorts|docs|all]
"""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FPS = 60
CAM = (1477, 0, 443, 321)                    # facecam x, y, w, h in source
GAME_ZOOM = (40, 230, 1422, 800)             # 1.35x punch-in crop, avoids facecam
GAP_MIN = 6.0                                # silences longer than this are dead air
GAP_KEEP = 1.2                               # keep this much on each side of a cut
AUDIO_GAIN_DB = 3.4                          # measured: source -17.4 LUFS -> ~-14
MAIN_SPEED = 1.1                             # long video only (the user's choice 2026-10-10); Shorts stay 1.0x
SFX_VOL = {"whoosh": 0.35, "boom": 0.55, "pop": 0.45, "ding": 0.35}

FIXES = {"Pilipino": "Filipino", "quest blog": "quest log", "Blacking": "Blocking",
         "No flare": "No flair", "Koopa": "Kupa", "Twiq": "Tweek", "Chin, Pokemon": "Chinpokomon", "Leela": "Lelac",
         "Carmetos": "Cartman's", "Kratty's": "Craig's", "man bear pig": "ManBearPig", "putters": "Butters",
         "Butter's Hammer": "Butters' hammer", "deuce bag": "douchebag", "Shitty Walks": "Shitty Wok"}


# Profanity (Shorts only, the user's choice): bleeped in the audio and starred out in the Shorts captions.
# The long video, transcript and SRT stay uncensored.
CUSS = re.compile(r"(fuck|shit|bitch|asshole|\bass\b|\basses\b|dumbass|jackass|\bdick(?=s?\b|ing|head|ed\b)|\bcock\b|cunt|puss(?:y|ies)"
                  r"|bastard|whore|\bslut|\bfag|retard|nigg)", re.I)
STARS = [(r"fuck", lambda m: m.group(0)[0] + "*" + m.group(0)[2:]),            # f*ck
         (r"shit", lambda m: m.group(0)[:2] + "*" + m.group(0)[3:]),           # sh*t
         (r"bitch", lambda m: m.group(0)[0] + "*" + m.group(0)[2:]),           # b*tch
         (r"\bass(?=hole|es\b|\b)", lambda m: m.group(0)[0] + "**"),           # a**, a**hole
         (r"(?<=dumb)ass|(?<=jack)ass", lambda m: m.group(0)[0] + "**"),
         (r"\bdick(?=s?\b|ing|head|ed\b)", lambda m: m.group(0)[0] + "*" + m.group(0)[2:]),           # d*ck
         (r"\bcock\b|cunt|\bslut", lambda m: m.group(0)[0] + "*" + m.group(0)[2:]),
         (r"puss(?=y|ies)", lambda m: m.group(0)[0] + "*" + m.group(0)[2:]),
         (r"bastard|whore", lambda m: m.group(0)[0] + "*" + m.group(0)[2:]),
         (r"\bfag|retard|nigg", lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1))]
BLEEP_PAD = 0.06
BLEEP_MIN = 0.25
BLEEP_MAX = 0.65                              # Whisper sometimes stretches shouted words
BLEEPS = []                                   # [(start, end)] in raw-stream seconds, set in main()


def censor(t):
    for pat, f in STARS:
        t = re.sub(pat, f, t, flags=re.I)
    return t


def fix(t):
    for a, b in FIXES.items():
        t = t.replace(a, b)
    return t


def find_bleeps(tr):
    out = []
    for s in tr["segments"]:
        for w in s["words"]:
            if CUSS.search(w["word"]):
                a, b = w["start"] - BLEEP_PAD, min(w["end"], w["start"] + BLEEP_MAX) + BLEEP_PAD
                if b - a < BLEEP_MIN:
                    c = (a + b) / 2; a, b = c - BLEEP_MIN / 2, c + BLEEP_MIN / 2
                out.append([max(0, a), b])
    out.sort(); merged = []
    for a, b in out:
        if merged and a <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], b)
        else: merged.append([a, b])
    return merged


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
    tr = json.load(open(w / "transcript.json"))
    scan = json.load(open(w / "scan.json"))
    plan = json.load(open(w / "plan.json"))
    return w, tr, scan, plan


def merge_words(words, merges):
    """Collapse misheard multi-word phrases into one word, e.g. 'Bauchika Wow Wow' -> 'BaoChickaWowWow'."""
    for phrase, repl in merges:
        parts = phrase.lower().split()
        i = 0
        while i <= len(words) - len(parts):
            got = [words[i + k]["word"].strip().lower().strip(".,!?") for k in range(len(parts))]
            if got == parts:
                tail = words[i + len(parts) - 1]["word"].strip()
                punct = tail[len(tail.rstrip(".,!?")):]
                words[i:i + len(parts)] = [{**words[i], "word": " " + repl + punct, "end": words[i + len(parts) - 1]["end"]}]
            i += 1
    return words


def classify(tr, scan, plan):
    """Return list of segments with speaker 'me' (streamer) or 'game'."""
    force_me, force_game = set(plan["force_me"]), set(plan["force_game"])
    drop = set(plan["drop"])
    out = []
    for i, s in enumerate(tr["segments"]):
        if not s["text"].strip() or i in drop:
            continue
        a, b = int(s["start"] * 2), max(int(s["start"] * 2) + 1, int(s["end"] * 2) + 1)
        subs = sum(1 for x in scan[a:b] if x[0] > 0.008) / max(1, len(scan[a:b]))
        who = "game" if subs > 0.5 else "me"
        if i in force_me: who = "me"
        if i in force_game: who = "game"
        words = merge_words([w for w in s["words"] if w["word"].strip()], plan.get("word_merge", []))
        cut = plan["split"].get(str(i))           # streamer words end before word index
        if cut is not None:
            out.append({"i": i, "who": "me", "words": words[:cut]})
            out.append({"i": i, "who": "game", "words": words[cut:]})
        else:
            out.append({"i": i, "who": who, "words": words})
    for o in out:
        o["text"] = fix("".join(w["word"] for w in o["words"]).strip())
        o["start"], o["end"] = o["words"][0]["start"], o["words"][-1]["end"]
    return [o for o in out if o["words"]]


def keep_ranges(tr, scan, plan, dur):
    iv = [(w["start"], w["end"]) for s in tr["segments"] if s["text"].strip() for w in s["words"]]
    iv += [(i / 2, i / 2 + 0.5) for i, x in enumerate(scan) if x[0] > 0.008]
    iv += [(e["t"], e["t"] + e.get("dur", 2)) for e in plan["effects"]]   # never cut an effect
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
        "Style: Cap,Arial,38,&H00FFFFFF,&H00FFFFFF,&H70000000,&H70000000,1,0,0,0,100,100,0,0,3,6,0,8,10,10,10,1",
        "Style: Pop,Impact,110,&H0000E5FF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,1,0,1,8,4,5,10,10,10,1",
        "Style: Title,Arial Black,44,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,0,0,1,4,2,1,60,60,60,1",
    ])
    ev = []
    cam_pops = [(e["t"], e["t"] + e["dur"]) for e in plan["effects"] if e["kind"] == "cam"]
    cx, cy, cw, ch = CAM
    small_pos = rf"{{\pos({cx + cw // 2},{cy + ch + 11})}}"
    big_pos = rf"{{\pos({1920 - cw - 6},{2 * ch + 26})}}"
    max_chars = max(14, int(20 * cw / 443))       # keep the box inside the facecam width
    for s in segs:
        if s["who"] != "me": continue
        for c in chunks(s["words"], max_chars):
            under_big_cam = any(a - 0.05 <= c["start"] < b for a, b in cam_pops)
            pos = big_pos if under_big_cam else small_pos
            ev.append(f"Dialogue: 0,{ts(c['start'],1)},{ts(c['end'],1)},Cap,,0,0,0,,{pos}{esc(c['text'])}")
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
    path.write_text(ASS_HEAD.format(w=1920, h=1080, styles=styles) + "\n".join(ev) + "\n")


def enable_expr(ranges):
    return "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in ranges) or "0"


def select_expr(keeps):
    return "+".join(f"gte(t,{a:.4f})*lt(t,{b:.4f})" for a, b in keeps)


def envelope_expr(keeps, fade=0.012):
    # per-cut micro fades so jump cuts don't click
    terms = [f"between(t,{a:.4f},{b:.4f})*min(1,min((t-{a:.4f})/{fade},({b:.4f}-t)/{fade}))" for a, b in keeps]
    return "+".join(terms)


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
    zoom = [(e["t"], e["t"] + e["dur"]) for e in plan["effects"] if e["kind"] == "zoom"]
    sfx = [(e["sfx"], e["t"]) for e in plan["effects"] if e.get("sfx")]
    sfx += [("whoosh", e["t"] - 0.15) for e in plan["effects"] if e["kind"] in ("cam", "zoom") and not e.get("sfx")]
    sargs, schains, slabels = sfx_inputs(sfx)
    cx, cy, cw, ch = CAM
    gx, gy, gw, gh = GAME_ZOOM
    sel = select_expr(keeps)
    (w / "select.txt").write_text(sel)
    vf = [
        f"[0:v]split=4[base][c][c2][g]",
        f"[c]crop={cw}:{ch}:{cx}:{cy},scale={cw*2}:{ch*2},pad={cw*2+12}:{ch*2+12}:6:6:white[cambig]",
        f"[c2]crop={cw}:{ch}:{cx}:{cy}[camsmall]",
        f"[g]crop={gw}:{gh}:{gx}:{gy},scale=1920:1080[gz]",
        f"[base][gz]overlay=enable='{enable_expr(zoom)}'[v1]",
        f"[v1][camsmall]overlay={cx}:{cy}:enable='{enable_expr(zoom)}'[v2]",
        f"[v2][cambig]overlay=W-w:0:enable='{enable_expr(cam)}'[v3]",
        f"[v3]ass='{ass}'[v4]",
        f"[v4]select='{sel}',setpts=N/FRAME_RATE/TB,setpts=PTS/{MAIN_SPEED},fps={FPS}[vout]",
    ]
    mute, bchain, blab = "", [], []            # long video is not bleeped (Shorts only)
    af = schains + bchain + [
        f"[0:a]{mute}volume={AUDIO_GAIN_DB}dB[ma]",
        f"[ma]{''.join(slabels + blab)}amix=inputs={len(slabels)+len(blab)+1}:normalize=0:duration=first[mix]",
        f"[mix]alimiter=limit=0.84:attack=5:release=60:level=disabled,asetnsamples=n=48:p=0,"
        f"volume='{envelope_expr(keeps)}':eval=frame,asetnsamples=n=800:p=0,"
        f"aselect='{sel}',asetpts=N/SR/TB,atempo={MAIN_SPEED}[aout]",
    ]
    graph = ";\n".join(vf + af)
    (w / "main_graph.txt").write_text(graph)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats", "-i", str(src)] + sargs + [
        "-filter_complex_script", str(w / "main_graph.txt"), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "h264_videotoolbox", "-b:v", "16M", "-maxrate", "24M", "-bufsize", "32M",
        "-profile:v", "high", "-r", str(FPS), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", str(out)]
    print("rendering main ->", out.name)
    subprocess.run(cmd, check=True)
    return out


# ---------- Shorts ----------
def short_ass(segs, a, b, sh, path):
    styles = "\n".join([
        "Style: Me,Arial Black,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,6,2,8,60,60,10,1",
        "Style: Game,Arial Black,56,&H0000E5FF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,6,2,8,60,60,10,1",
        "Style: Hook,Arial Black,58,&H00000000,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,3,18,0,5,60,60,10,1",
    ])
    ev = []
    for s in segs:
        if s["end"] < a or s["start"] > b: continue
        ws = [x for x in s["words"] if a <= x["start"] < b]
        for c in chunks(ws, 22 if s["who"] == "me" else 30):
            ev.append(f"Dialogue: 0,{ts(c['start']-a,1)},{ts(min(c['end'],b)-a,1)},"
                      f"{'Me' if s['who']=='me' else 'Game'},,0,0,0,,{{\\pos(540,830)}}{esc(censor(c['text']).upper() if s['who']=='me' else censor(c['text']))}")
    ev.append(f"Dialogue: 1,{ts(0,1)},{ts(3.2,1)},Hook,,0,0,0,,{{\\pos(540,690)\\fscx120\\fscy120\\t(0,150,\\fscx100\\fscy100)}}{esc(sh['hook'])}")
    path.write_text(ASS_HEAD.format(w=1080, h=1920, styles=styles) + "\n".join(ev) + "\n")


def render_short(name, w, src, segs, keeps, sh, n):
    a, b = sh["start"], sh["end"]
    local = [(max(x, a) - a, min(y, b) - a) for x, y in keeps if y > a and x < b]
    local = [(snap(x), snap(y)) for x, y in local]
    ass = w / f"short{n}.ass"
    short_ass(segs, a, b, sh, ass)
    cx, cy, cw, ch = CAM
    sel = select_expr(local)
    sfx = [(name, t - a) for name, t in sh.get("sfx", [])] + [("whoosh", 0.0)]
    sargs, schains, slabels = sfx_inputs(sfx)
    mute, bchain, blab = bleep_audio(a, b - a)
    graph = ";\n".join([
        "[0:v]split=2[c][g]",
        f"[c]crop={cw}:{ch}:{cx}:{cy},scale=1080:782[top]",
        "[g]crop=882:930:520:0,scale=1080:1138[bot]",
        "[top][bot]vstack[st]",
        f"[st]ass='{ass}'[s1]",
        f"[s1]select='{sel}',setpts=N/FRAME_RATE/TB[vout]",
    ] + schains + bchain + [
        f"[0:a]{mute}volume={AUDIO_GAIN_DB}dB[ma]",
        f"[ma]{''.join(slabels + blab)}amix=inputs={len(slabels)+len(blab)+1}:normalize=0:duration=first[mix]",
        f"[mix]alimiter=limit=0.84:attack=5:release=60:level=disabled,asetnsamples=n=48:p=0,"
        f"volume='{envelope_expr(local)}':eval=frame,asetnsamples=n=800:p=0,"
        f"aselect='{sel}',asetpts=N/SR/TB[aout]",
    ])
    gpath = w / f"short{n}_graph.txt"
    gpath.write_text(graph)
    out_dir = ROOT / "Ouput" / name / "Shorts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name} - Short {n} - {sh['name']}.mp4"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
           "-i", str(src)] + sargs + [
        "-filter_complex_script", str(gpath), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "h264_videotoolbox", "-b:v", "12M", "-profile:v", "high", "-r", str(FPS), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out)]
    print(f"rendering short {n} ({sum(y-x for x,y in local):.1f}s) ->", out.name)
    subprocess.run(cmd, check=True)


# ---------- Docs ----------
def write_docs(name, segs, keeps, plan, tr):
    f0 = src_to_edit(keeps)
    f = lambda t: f0(t) / MAIN_SPEED                # long video plays at MAIN_SPEED
    out_dir = ROOT / "Ouput" / name; out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"{plan['title_options'][0]}", "Full transcript (timestamps match the edited YouTube video).",
             "LELAC = streamer, GAME = in-game dialogue / narration. Raw-stream times in [brackets].", ""]
    for s in segs:
        lines.append(f"{ts(f(s['start']))}  [{ts(s['start'])}]  {'LELAC' if s['who']=='me' else 'GAME '}: {s['text']}")
    (out_dir / f"{name} - Transcript.txt").write_text("\n".join(lines) + "\n")

    # SRT of everything (upload as YouTube closed captions for accessibility + SEO)
    srt, k = [], 1
    def st(x): return f"{int(x//3600):02d}:{int(x%3600//60):02d}:{int(x%60):02d},{int(round(x%1*1000))%1000:03d}"
    for s in segs:
        for c in chunks(s["words"], 42):
            a, b = f(c["start"]), f(c["end"])
            if b - a < 0.2: continue
            srt.append(f"{k}\n{st(a)} --> {st(b)}\n{'' if s['who']=='me' else '[Game] '}{c['text']}\n"); k += 1
    (out_dir / f"{name} - Captions.srt").write_text("\n".join(srt))

    ch = "\n".join(f"{ts(f(t)) if f(t) > 0 else '0:00'} {name}" for t, name in plan["chapters"])
    total = sum(b - a for a, b in keeps) / MAIN_SPEED
    meta = [f"FINAL LENGTH: {ts(total)} at {MAIN_SPEED}x speed  (raw stream {ts(plan['raw_dur'])}; dead air removed, then sped up)", "",
            "TITLE OPTIONS", *[f"  {i+1}. {t}" for i, t in enumerate(plan["title_options"])], "",
            "DESCRIPTION (paste as-is)", "-" * 40, plan["description"].replace("{CHAPTERS}", ch), "-" * 40, "",
            "TAGS (comma-separated, paste into YouTube tags box)", ", ".join(plan["tags"]), "",
            "SHORTS", *[f"  Short {i+1}: {s['name']}\n     Title: {s['title']}\n     Raw-stream source: {ts(s['start'])}-{ts(s['end'])}"
                       for i, s in enumerate(plan["shorts"])], "",
            "THUMBNAIL IDEAS", plan["thumbnails"].strip(), ""]
    (out_dir / f"{name} - YouTube Upload Kit.txt").write_text("\n".join(meta))
    print("docs written; final length", ts(total))


def main():
    base = sys.argv[1]
    what = sys.argv[2] if len(sys.argv) > 2 else "all"
    w, tr, scan, plan = load(base)
    global MAIN_SPEED
    MAIN_SPEED = plan.get("main_speed", MAIN_SPEED)
    global CAM, AUDIO_GAIN_DB                     # per-episode overrides (OBS layout / mic changes)
    CAM = tuple(plan.get("cam", CAM))
    AUDIO_GAIN_DB = plan.get("audio_gain_db", AUDIO_GAIN_DB)
    global BLEEPS
    BLEEPS = [] if plan.get("no_bleep") else find_bleeps(tr)
    print(f"{len(BLEEPS)} bleeps")
    src = ROOT / "Raw" / f"{plan['raw']}"
    if not src.exists():                          # finished episodes get moved to Raw Archive/
        src = ROOT / "Raw Archive" / f"{plan['raw']}"
    name = Path(plan["raw"]).stem
    segs = classify(tr, scan, plan)
    keeps = keep_ranges(tr, scan, plan, plan["raw_dur"])
    json.dump(keeps, open(w / "keeps.json", "w"))
    print(f"{len(keeps)} keep ranges, {sum(b-a for a,b in keeps)/60:.1f} min kept")
    if what in ("docs", "all"): write_docs(name, segs, keeps, plan, tr)
    if what in ("shorts", "all"):
        only = [int(x) for x in sys.argv[3:]] or range(1, len(plan["shorts"]) + 1)
        for n in only: render_short(name, w, src, segs, keeps, plan["shorts"][n - 1], n)
    if what in ("main", "all"): render_main(name, w, src, segs, keeps, plan)


if __name__ == "__main__":
    main()
