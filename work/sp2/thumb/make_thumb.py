import os, sys; sys.path.insert(0, os.getcwd())  # run from the Streams folder
from pipeline_env import font_path
import sys
from PIL import Image, ImageFilter, ImageDraw, ImageFont, ImageEnhance, ImageChops

D="work/sp2/thumb/"
import sys
LOGO="--logo" in sys.argv
W,H=1280,720
def stroke(cut, px, color=(255,255,255,255)):
    a=cut.split()[3].point(lambda v:255 if v>100 else 0)
    big=a.filter(ImageFilter.GaussianBlur(px*0.6)).point(lambda v:255 if v>8 else 0).filter(ImageFilter.GaussianBlur(1))
    s=Image.new("RGBA",cut.size,color); s.putalpha(big)
    sh=Image.new("RGBA",cut.size,(0,0,0,170)); sh.putalpha(big.filter(ImageFilter.GaussianBlur(10)).point(lambda v:int(v*0.7)))
    out=Image.new("RGBA",(cut.width+40,cut.height+40),(0,0,0,0))
    out.alpha_composite(sh,(26,30)); out.alpha_composite(s,(20,20)); out.alpha_composite(cut,(20,20)); return out
def trim(im):
    return im.crop(im.split()[3].getbbox())

# --- Leela ---
face=Image.open(D+"face_5543.5.png").convert("RGB")
face=face.resize((face.width*3,face.height*3),Image.LANCZOS).filter(ImageFilter.UnsharpMask(2,70,3))
face=ImageEnhance.Color(face).enhance(1.08); face=ImageEnhance.Contrast(face).enhance(1.06)
lc=Image.open(D+'lee_cut.png').convert('RGBA'); al=lc.split()[3]
lee=face.convert('RGBA'); lee.putalpha(al); lee=trim(lee)
lee=lee.resize((int(lee.width*600/lee.height),600),Image.LANCZOS)
lee=stroke(lee,9)

# --- Cartman ---
cart=Image.open(D+"khan_clean.png").convert("RGBA")
rgb=ImageEnhance.Color(cart.convert("RGB")).enhance(1.2).convert("RGBA"); rgb.putalpha(cart.split()[3]); cart=trim(rgb)
cart=cart.resize((int(cart.width*640/cart.height),640),Image.LANCZOS)
cart=stroke(cart,8)

# --- background: blurred Kupa Keep + sunburst ---
bg=Image.open(D+"khan_5316.png").convert("RGB").resize((W,H)).filter(ImageFilter.GaussianBlur(14))
bg=ImageEnhance.Brightness(bg).enhance(0.55).convert("RGBA")
burst=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(burst); cx,cy=W*0.5,H*0.5
import math
for i in range(24):
    a0=i*2*math.pi/24; a1=a0+math.pi/24
    d.polygon([(cx,cy),(cx+2000*math.cos(a0),cy+2000*math.sin(a0)),(cx+2000*math.cos(a1),cy+2000*math.sin(a1))],fill=(255,200,0,70))
glow=Image.new("L",(W,H),0); ImageDraw.Draw(glow).ellipse((cx-420,cy-420,cx+420,cy+420),fill=255)
glow=glow.filter(ImageFilter.GaussianBlur(120)); gl=Image.new("RGBA",(W,H),(255,170,0,0)); gl.putalpha(glow.point(lambda v:int(v*0.55)))
bg.alpha_composite(burst); bg.alpha_composite(gl)
vig=Image.new("L",(W,H),0); ImageDraw.Draw(vig).ellipse((-250,-200,W+250,H+200),fill=255)
vig=vig.filter(ImageFilter.GaussianBlur(120)); dark=Image.new("RGBA",(W,H),(0,0,0,255)); dark.putalpha(ImageChops.invert(vig).point(lambda v:int(v*0.8)))
bg.alpha_composite(dark)

bg.alpha_composite(cart,(W-cart.width+20,H-cart.height+20))
bg.alpha_composite(lee,(-30,H-lee.height+20))


# --- game logo (keyed from title screen) ---
src=Image.open("work/sp1/thumb/title.png").convert("RGB").crop((420,130,1460,680))
lum=src.convert("L")
al=lum.point(lambda v:max(0,min(255,(v-55)*6)))
logo=src.convert("RGBA"); logo.putalpha(al); logo=trim(logo)
logo=ImageEnhance.Brightness(logo).enhance(1.1)
logo=logo.resize((315,int(logo.height*315/logo.width)),Image.LANCZOS)
logo=stroke(logo,5,(0,0,0,255))
if LOGO: bg.alpha_composite(logo,(6,4))

# --- text ---
def txt(s,size,xy,fill,rot=0):
    f=ImageFont.truetype(font_path("Impact"),size)
    l,t,r,b=f.getbbox(s); im=Image.new("RGBA",(r-l+60,b-t+60),(0,0,0,0)); dd=ImageDraw.Draw(im)
    dd.text((30-l+6,30-t+8),s,font=f,fill=(0,0,0,200),stroke_width=14,stroke_fill=(0,0,0,200))
    dd.text((30-l,30-t),s,font=f,fill=fill,stroke_width=12,stroke_fill=(0,0,0,255))
    im=im.rotate(rot,expand=True,resample=Image.BICUBIC); bg.alpha_composite(im,(int(xy[0]-im.width/2),int(xy[1]))); 
txt("WE BEAT",100,(660,4),(255,255,255,255),rot=3)
txt("GENGHIS KHAN!",112,(660,112),(255,226,0,255),rot=3)
O="Ouput/South Park Stick of Truth Part 2/South Park Stick of Truth Part 2 - Thumbnail"+(" v2 (logo)" if LOGO else "")
out=bg.convert("RGB"); out.save(O+".png"); out.save(O+".jpg",quality=92)
print("ok")
