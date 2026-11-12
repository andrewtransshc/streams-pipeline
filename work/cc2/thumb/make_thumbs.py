# Copycat thumbnails (1280x720) for cc0 / cc1 / cc2. Cutouts come from cutouts.py (rembg).
# Run from Streams/:  .venv/bin/python (Windows: .venv/Scripts/python.exe) work/cc2/thumb/make_thumbs.py [cc0 cc1 cc2]
import os, sys; sys.path.insert(0, os.getcwd())  # run from the Streams folder
from pipeline_env import font_path
import math, sys
from PIL import Image, ImageFilter, ImageDraw, ImageFont, ImageEnhance, ImageChops

W, H = 1280, 720
IMPACT = font_path("Impact")
OUT = {"cc0": "Ouput/Copycat FaceMask/Copycat FaceMask - Thumbnail",
       "cc1": "Ouput/Copycat Part 1 (Intro)/Copycat Part 1 (Intro) - Thumbnail",
       "cc2": "Ouput/Copycat Part 2/Copycat Part 2 - Thumbnail"}


def trim(im):
    return im.crop(im.split()[3].getbbox())


def stroke(cut, px, color=(255, 255, 255, 255)):
    a = cut.split()[3].point(lambda v: 255 if v > 100 else 0)
    big = a.filter(ImageFilter.GaussianBlur(px * 0.6)).point(lambda v: 255 if v > 8 else 0).filter(ImageFilter.GaussianBlur(1))
    s = Image.new("RGBA", cut.size, color); s.putalpha(big)
    sh = Image.new("RGBA", cut.size, (0, 0, 0, 170)); sh.putalpha(big.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.7)))
    out = Image.new("RGBA", (cut.width + 40, cut.height + 40), (0, 0, 0, 0))
    out.alpha_composite(sh, (26, 30)); out.alpha_composite(s, (20, 20)); out.alpha_composite(cut, (20, 20))
    return out


def person(path, h, color=1.08, bright=1.0):
    im = trim(Image.open(path).convert("RGBA"))
    rgb = ImageEnhance.Color(im.convert("RGB")).enhance(color)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.06)
    rgb = ImageEnhance.Brightness(rgb).enhance(bright).convert("RGBA")
    rgb.putalpha(im.split()[3])
    rgb = rgb.resize((int(rgb.width * h / rgb.height), h), Image.LANCZOS)
    return stroke(rgb, 9)


def vignette(bg, amt=0.8):
    vig = Image.new("L", (W, H), 0); ImageDraw.Draw(vig).ellipse((-250, -200, W + 250, H + 200), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 255)); dark.putalpha(ImageChops.invert(vig).point(lambda v: int(v * amt)))
    bg.alpha_composite(dark)


def rays(bg, cx, cy, rgb, alpha, n=24):
    burst = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(burst)
    for i in range(n):
        a0 = i * 2 * math.pi / n; a1 = a0 + math.pi / n
        d.polygon([(cx, cy), (cx + 2000 * math.cos(a0), cy + 2000 * math.sin(a0)),
                   (cx + 2000 * math.cos(a1), cy + 2000 * math.sin(a1))], fill=rgb + (alpha,))
    bg.alpha_composite(burst.filter(ImageFilter.GaussianBlur(2)))


def logo(width):
    """COPYCAT logo keyed off the title screen (white on dark sky). The facecam corner is masked out."""
    src = Image.open("work/cc0/thumb/title.png").convert("RGB")
    lum = src.convert("L").point(lambda v: max(0, min(255, (v - 150) * 4)))
    ImageDraw.Draw(lum).rectangle((1540, 0, 1920, 272), fill=0)
    ImageDraw.Draw(lum).rectangle((930, 350, 1000, 420), fill=0)          # falling leaf under the C
    lum = lum.filter(ImageFilter.MinFilter(7)).filter(ImageFilter.MaxFilter(7))   # drop falling-leaf specks
    lg = src.convert("RGBA"); lg.putalpha(lum)
    lg = trim(lg.crop((860, 120, 1800, 420)))
    lg = lg.resize((width, int(lg.height * width / lg.width)), Image.LANCZOS)
    return stroke(lg, 6, (0, 0, 0, 255))


def txt(bg, s, size, xy, fill, rot=0, anchor="c"):
    f = ImageFont.truetype(IMPACT, size)
    l, t, r, b = f.getbbox(s); im = Image.new("RGBA", (r - l + 60, b - t + 60), (0, 0, 0, 0)); dd = ImageDraw.Draw(im)
    dd.text((30 - l + 6, 30 - t + 8), s, font=f, fill=(0, 0, 0, 200), stroke_width=14, stroke_fill=(0, 0, 0, 200))
    dd.text((30 - l, 30 - t), s, font=f, fill=fill, stroke_width=12, stroke_fill=(0, 0, 0, 255))
    im = im.rotate(rot, expand=True, resample=Image.BICUBIC)
    x = xy[0] - im.width / 2 if anchor == "c" else xy[0]
    bg.alpha_composite(im, (int(x), int(xy[1])))


def title_bg(blur, bright):   # crop skips the menu, logo and sponsor strip
    """Copycat title screen (porch at night + cat silhouette), facecam cropped off."""
    bg = Image.open("work/cc0/thumb/title.png").convert("RGB").crop((290, 390, 1426, 1029)).resize((W, H), Image.LANCZOS)
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(blur))).enhance(bright)
    return bg.convert("RGBA")


def cc2():
    bg = Image.open("work/cc2/thumb/bg_1561.png").convert("RGB").crop((120, 230, 1380, 939)).resize((W, H), Image.LANCZOS)
    bg = ImageEnhance.Color(bg).enhance(1.15)
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(1.2))).enhance(0.8).convert("RGBA")
    vignette(bg, 0.75)
    # red ring + arrow on Olive walking back to the car
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    d.ellipse((900, 150, 1080, 450), outline=(0, 0, 0, 255), width=16)
    d.ellipse((900, 150, 1080, 450), outline=(235, 30, 30, 255), width=9)
    bg.alpha_composite(ov)
    cat = Image.open("work/cc2/thumb/cat_cut.png").convert("RGBA")
    cat = trim(cat); cat = cat.resize((int(cat.width * 360 / cat.height), 360), Image.LANCZOS)
    bg.alpha_composite(cat, (W - cat.width - 10, H - cat.height + 10))
    lee = person("work/cc2/thumb/lelac_cut.png", 560)
    bg.alpha_composite(lee, (-40, H - lee.height + 20))
    txt(bg, "SHE LEFT ME?!", 150, (790, 8), (255, 255, 255, 255), rot=3)
    lg = logo(300); bg.alpha_composite(lg, (600, H - lg.height - 2))
    return bg


def cc1():
    bg = title_bg(7, 0.75)
    rays(bg, W * 0.33, H * 0.62, (255, 190, 90), 38)
    vignette(bg, 0.7)
    lee = person("work/cc1/thumb/lelac_cut.png", 600)
    bg.alpha_composite(lee, (-30, H - lee.height + 20))
    # a couple of cartoon tears under the grin, for the "this game will make me cry" joke
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for x, y, r in [(338, 330, 14), (508, 330, 14)]:
        d.ellipse((x - r - 4, y - 4, x + r + 4, y + 2 * r + 4), fill=(0, 0, 0, 255))
        d.polygon([(x - r - 3, y + r), (x + r + 3, y + r), (x, y - 2 * r - 6)], fill=(0, 0, 0, 255))
        d.ellipse((x - r, y, x + r, y + 2 * r), fill=(110, 200, 255, 255))
        d.polygon([(x - r + 1, y + r), (x + r - 1, y + r), (x, y - 2 * r)], fill=(110, 200, 255, 255))
    bg.alpha_composite(ov)
    txt(bg, "SAD CAT GAME", 112, (875, 210), (255, 255, 255, 255), rot=3)
    txt(bg, "ON MY PERIOD", 112, (880, 340), (255, 120, 170, 255), rot=3)
    lg = logo(440); bg.alpha_composite(lg, (W - lg.width - 60, 30))
    return bg


def cc0():
    bg = title_bg(6, 0.6)
    rays(bg, W * 0.38, H * 0.55, (170, 220, 255), 40)
    vignette(bg, 0.7)
    lee = person("work/cc0/thumb/lelac_cut.png", 640, color=1.05, bright=1.04)
    bg.alpha_composite(lee, (-10, H - lee.height + 20))
    txt(bg, "SELF-CARE", 130, (950, 200), (255, 255, 255, 255), rot=3)
    txt(bg, "BEFORE I CRY", 104, (955, 345), (120, 210, 255, 255), rot=3)
    lg = logo(400); bg.alpha_composite(lg, (W - lg.width - 90, 40))
    return bg


for wid in sys.argv[1:] or ["cc0", "cc1", "cc2"]:
    out = globals()[wid]().convert("RGB")
    out.save(OUT[wid] + ".png"); out.save(OUT[wid] + ".jpg", quality=92)
    print(wid, "ok")
