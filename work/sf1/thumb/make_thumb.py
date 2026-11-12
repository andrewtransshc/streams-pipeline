# Split Fiction Part 1 thumbnail: "2 GAMES IN 1?!" — sci-fi Zoe (left) | fantasy Zoe (right), jagged split,
# Lelac + Andrew cutout bottom-center, small game logo bottom-right.
import os, sys; sys.path.insert(0, os.getcwd())  # run from the Streams folder
from pipeline_env import font_path
import math, random
from PIL import Image, ImageFilter, ImageDraw, ImageFont, ImageEnhance, ImageChops
D = "work/sf1/thumb/"; W, H = 1280, 720
OUT = "Ouput/Split Fiction Part 1/Split Fiction Part 1 - Thumbnail"

def stroke(cut, px, color=(255, 255, 255, 255)):
    a = cut.split()[3].point(lambda v: 255 if v > 100 else 0)
    big = a.filter(ImageFilter.GaussianBlur(px * 0.6)).point(lambda v: 255 if v > 8 else 0).filter(ImageFilter.GaussianBlur(1))
    s = Image.new("RGBA", cut.size, color); s.putalpha(big)
    sh = Image.new("RGBA", cut.size, (0, 0, 0, 170)); sh.putalpha(big.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.7)))
    out = Image.new("RGBA", (cut.width + 40, cut.height + 40), (0, 0, 0, 0))
    out.alpha_composite(sh, (26, 30)); out.alpha_composite(s, (20, 20)); out.alpha_composite(cut, (20, 20)); return out
def pad(im, p):
    o = Image.new("RGBA", (im.width + 2 * p, im.height + 2 * p), (0, 0, 0, 0)); o.alpha_composite(im, (p, p)); return o
def fit(path, box, zoom_h):
    im = Image.open(path).convert("RGB").crop(box)
    im = im.resize((int(im.width * zoom_h / im.height), zoom_h), Image.LANCZOS)
    im = ImageEnhance.Color(im).enhance(1.35); im = ImageEnhance.Contrast(im).enhance(1.12)
    return im

# --- two worlds ---
left = fit(D + "full_1834.png", (700, 120, 1540, 900), H)      # sci-fi Zoe, neon suit
right = fit(D + "full_430.png", (360, 120, 1200, 900), H)
right = ImageEnhance.Brightness(right).enhance(1.35)      # fantasy Zoe, fireball
bg = Image.new("RGBA", (W, H))
bg.paste(left.crop(((left.width - W // 2 - 140) // 2 + 70, 0, (left.width - W // 2 - 140) // 2 + 70 + W // 2 + 140, H)), (-40, 0))
r = right.crop(((right.width - W // 2 - 140) // 2, 0, (right.width - W // 2 - 140) // 2 + W // 2 + 140, H))
# jagged split line
random.seed(7); pts = []; y = -20; x = W // 2
while y < H + 20:
    pts.append((x + random.choice([-1, 1]) * random.randint(18, 42), y)); y += random.randint(55, 90)
mask = Image.new("L", (W, H), 0); ImageDraw.Draw(mask).polygon(pts + [(W + 10, H + 20), (W + 10, -20)], fill=255)
rr = Image.new("RGBA", (W, H)); rr.paste(r, (W // 2 - 100, 0)); bg.paste(rr, (0, 0), mask)
# darken a little toward bottom/top so text + faces pop
grad = Image.linear_gradient("L").resize((W, H)); dark = Image.new("RGBA", (W, H), (0, 0, 0, 255))
dark.putalpha(grad.point(lambda v: int(max(0, v - 120) * 0.9))); bg.alpha_composite(dark)
top = Image.new("RGBA", (W, H), (0, 0, 0, 255)); top.putalpha(ImageChops.invert(grad).point(lambda v: int(max(0, v - 150) * 1.2))); bg.alpha_composite(top)
# glowing split line
ln = Image.new("L", (W, H), 0); ImageDraw.Draw(ln).line(pts, fill=255, width=10, joint="curve")
glow = Image.new("RGBA", (W, H), (255, 255, 255, 0)); glow.putalpha(ln.filter(ImageFilter.GaussianBlur(14)))
core = Image.new("RGBA", (W, H), (255, 255, 255, 0)); core.putalpha(ln.filter(ImageFilter.GaussianBlur(1)))
bg.alpha_composite(glow); bg.alpha_composite(glow); bg.alpha_composite(core)

# --- Lelac + Andrew ---
f = Image.open(D + "faces_combo.png").convert("RGBA")   # Lelac @1340.4 + Andrew @2474.6
rgb = f.convert("RGB").filter(ImageFilter.UnsharpMask(2, 70, 3)); rgb = ImageEnhance.Color(rgb).enhance(1.12)
rgb = ImageEnhance.Brightness(rgb).enhance(1.05).convert("RGBA"); rgb.putalpha(f.split()[3]); f = rgb.crop(rgb.split()[3].getbbox())
f = f.resize((int(f.width * 450 / f.height), 450), Image.LANCZOS)
f = stroke(pad(f, 10), 9)
bg.alpha_composite(f, ((W - f.width) // 2 - 10, H - f.height + 34))

# --- text ---
font = ImageFont.truetype(font_path("Impact"), 150)
txt = "2 GAMES IN 1?!"
tw = ImageDraw.Draw(bg).textbbox((0, 0), txt, font=font)
tl = Image.new("RGBA", (tw[2] + 60, tw[3] + 60), (0, 0, 0, 0)); d = ImageDraw.Draw(tl)
d.text((30, 18), txt, font=font, fill=(255, 226, 0), stroke_width=12, stroke_fill=(0, 0, 0))
sh = Image.new("RGBA", tl.size, (0, 0, 0, 200)); sh.putalpha(tl.split()[3].filter(ImageFilter.GaussianBlur(10)))
tl2 = Image.new("RGBA", tl.size); tl2.alpha_composite(sh, (6, 10)); tl2.alpha_composite(tl)
tl2 = tl2.rotate(-3, expand=True, resample=Image.BICUBIC)
if tl2.width > W - 40: tl2 = tl2.resize((W - 40, int(tl2.height * (W - 40) / tl2.width)), Image.LANCZOS)
bg.alpha_composite(tl2, ((W - tl2.width) // 2, -10))

# --- logo (small, bottom-right) ---
logo = Image.open(D + "logo_final.png").convert("RGBA")
logo = logo.resize((300, int(logo.height * 300 / logo.width)), Image.LANCZOS)
logo = stroke(pad(logo, 6), 4, (0, 0, 0, 255))
bg.alpha_composite(logo, (W - logo.width - 6, H - logo.height - 8))

out = bg.convert("RGB"); out.save(OUT + ".png"); out.save(OUT + ".jpg", quality=92)
print("saved", OUT)
