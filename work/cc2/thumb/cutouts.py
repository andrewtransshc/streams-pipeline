# rembg cutouts for the Copycat thumbnails. Run with a venv that has rembg (CPU provider only: CoreML hangs on this Mac).
from rembg import new_session, remove
from PIL import Image, ImageFilter
sess = new_session("isnet-general-use", providers=["CPUExecutionProvider"])
def face(src, dst):
    im = Image.open(src).convert("RGB")
    im = im.resize((im.width * 3, im.height * 3), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 70, 3))
    remove(im, session=sess).save(dst); print(dst)
face("work/cc2/thumb/face_1467.9.png", "work/cc2/thumb/lelac_cut.png")
face("work/cc1/thumb/face_24.5.png", "work/cc1/thumb/lelac_cut.png")
face("work/cc0/thumb/face_160.png", "work/cc0/thumb/lelac_cut.png")
cat = Image.open("work/cc2/thumb/bg_1561.png").convert("RGB").crop((1300, 560, 1920, 1080))
remove(cat, session=sess).save("work/cc2/thumb/cat_cut.png"); print("cat")
