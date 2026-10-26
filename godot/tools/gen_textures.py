"""Paint the low-res retro textures for the Godot prototype (godot/textures/).

Everything is drawn procedurally so the look can be tweaked here and regenerated:
    python godot/tools/gen_textures.py
Facades are 4 bays x 4 floors (12 x 11.2 m) for the flats, so world UVs line up with windows.
"""
import os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(__file__), '..', 'textures')
os.makedirs(OUT, exist_ok=True)
rnd = random.Random(3)

def grain(img, amount, seed, scale=1):
    a = np.array(img).astype(np.float32)
    r = np.random.default_rng(seed)
    h, w = a.shape[:2]
    n = r.normal(0, amount, (h // scale, w // scale, 1))
    if scale > 1: n = np.kron(n, np.ones((scale, scale, 1)))
    a[..., :3] += n
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

def tileable_noise(size, cells, seed):
    r = np.random.default_rng(seed)
    small = r.random((cells, cells))
    big = np.tile(small, (3, 3))
    im = Image.fromarray((big * 255).astype(np.uint8)).resize((size * 3, size * 3), Image.BICUBIC)
    return np.array(im)[size:2 * size, size:2 * size].astype(np.float32) / 255 - 0.5

def save(img, name):
    img.save(os.path.join(OUT, name + '.png'))

WIN_GLASS = [(70, 90, 110), (58, 74, 96), (96, 112, 120), (120, 104, 70), (150, 128, 84), (64, 80, 92)]
CURTAIN = [(170, 120, 80), (140, 150, 170), (190, 170, 120), (120, 70, 60)]

def facade(name, wall, seam, bays=4, floors=4, px=32, win=(0.62, 0.55), balcony=0.0, frame=(220, 220, 214), stain=0):
    W, H = bays * px, floors * px
    im = Image.new('RGB', (W, H), wall)
    d = ImageDraw.Draw(im)
    for f in range(floors):
        for b in range(bays):
            x0, y0 = b * px, f * px
            d.rectangle([x0, y0, x0 + px - 1, y0 + px - 1], outline=seam)        # panel joints
            ww, wh = int(px * win[0]), int(px * win[1])
            wx, wy = x0 + (px - ww) // 2, y0 + int(px * 0.18)
            d.rectangle([wx - 1, wy - 1, wx + ww, wy + wh], fill=frame)
            glass = rnd.choice(WIN_GLASS)
            d.rectangle([wx, wy, wx + ww - 1, wy + wh - 1], fill=glass)
            if rnd.random() < 0.35:                                            # curtains
                d.rectangle([wx, wy, wx + ww // 3, wy + wh - 1], fill=rnd.choice(CURTAIN))
            d.line([wx + ww // 2, wy, wx + ww // 2, wy + wh - 1], fill=frame)
            d.line([wx, wy + wh // 3, wx + ww - 1, wy + wh // 3], fill=frame)
            if balcony and rnd.random() < balcony:                             # glazed or open balcony
                by = y0 + int(px * 0.6)
                col = rnd.choice([(200, 196, 186), (150, 150, 146), (176, 150, 120), (120, 130, 140)])
                d.rectangle([x0 + 3, by, x0 + px - 4, y0 + px - 3], fill=col)
                d.line([x0 + 3, by, x0 + px - 4, by], fill=(90, 90, 90))
    im = grain(im, 7, hash(name) % 100)
    if stain:                                                                  # rain streaks under joints
        a = np.array(im).astype(np.float32)
        n = tileable_noise(W, 8, 5)[:, :W]
        a *= (1 - stain * np.clip(n[:H, :W] + 0.3, 0, 1))[..., None]
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    save(im, name)

facade('facade_panel', (186, 182, 172), (150, 146, 138), balcony=0.45, stain=0.18)
facade('facade_panel_b', (196, 186, 160), (160, 150, 128), balcony=0.3, stain=0.15)
facade('facade_khrush', (178, 140, 112), (150, 112, 90), win=(0.5, 0.55), balcony=0.2, frame=(236, 232, 220), stain=0.12)
facade('facade_public', (214, 196, 150), (190, 170, 128), bays=4, floors=2, px=32, win=(0.78, 0.6), frame=(240, 240, 236), stain=0.1)

# garages: brick wall with metal doors, 1 "floor"
W, H = 128, 32
im = Image.new('RGB', (W, H), (132, 92, 72))
d = ImageDraw.Draw(im)
for y in range(0, H, 3):
    off = 0 if (y // 3) % 2 else 3
    for x in range(-off, W, 6):
        d.rectangle([x, y, x + 5, y + 2], outline=(110, 74, 58))
for i in range(4):
    col = rnd.choice([(70, 96, 84), (92, 70, 60), (84, 90, 104), (120, 110, 70)])
    d.rectangle([i * 32 + 4, 8, i * 32 + 27, 31], fill=col)
    for y in range(10, 31, 3): d.line([i * 32 + 5, y, i * 32 + 26, y], fill=tuple(c - 14 for c in col))
save(grain(im, 8, 11), 'facade_garage')

# industrial: corrugated metal with a strip of windows
W, H = 64, 64
im = Image.new('RGB', (W, H), (128, 138, 146))
d = ImageDraw.Draw(im)
for x in range(0, W, 4): d.line([x, 0, x, H], fill=(108, 118, 126))
d.rectangle([0, 10, W, 20], fill=(70, 86, 96))
for x in range(0, W, 8): d.line([x, 10, x, 20], fill=(180, 186, 190))
save(grain(im, 9, 12), 'facade_industrial')

def tile(name, base, amount, cells, seed, extra=None, size=64):
    n = tileable_noise(size, cells, seed) * amount + tileable_noise(size, size // 2, seed + 1) * amount * 0.6
    a = np.ones((size, size, 3), np.float32) * np.array(base, np.float32) + n[..., None]
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if extra: extra(ImageDraw.Draw(im), size)
    save(grain(im, 5, seed + 2), name)

tile('roof', (84, 82, 80), 40, 6, 20)
def cracks(d, s):
    for _ in range(5):
        x, y = rnd.randrange(s), rnd.randrange(s)
        for _ in range(6):
            nx, ny = x + rnd.randint(-6, 6), y + rnd.randint(-6, 6)
            d.line([x, y, nx, ny], fill=(58, 58, 60)); x, y = nx, ny
tile('asphalt', (92, 92, 96), 34, 4, 30, cracks)
def slabs(d, s):
    for i in range(0, s, 16):
        d.line([i, 0, i, s], fill=(128, 124, 116)); d.line([0, i, s, i], fill=(128, 124, 116))
tile('pavement', (160, 154, 140), 26, 4, 40, slabs)
def steps(d, s):
    for i in range(0, s, 8):
        d.rectangle([0, i, s, i + 1], fill=(110, 108, 104)); d.line([0, i + 2, s, i + 2], fill=(190, 186, 178))
tile('stairs', (156, 152, 144), 18, 4, 50, steps)
tile('concrete', (168, 164, 156), 30, 4, 60)

# tree card: a rounded crown on a trunk, alpha cut-out
W, H = 64, 96
im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rectangle([29, 56, 34, 95], fill=(78, 62, 48, 255))
for _ in range(40):
    r = rnd.randint(7, 13)
    x, y = rnd.gauss(32, 9), rnd.gauss(36, 12)
    shade = rnd.uniform(0.75, 1.15)
    col = tuple(int(c * shade) for c in (66, 104, 44)) + (255,)
    d.ellipse([x - r, y - r, x + r, y + r], fill=col)
save(im, 'tree_birch')
im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rectangle([30, 70, 33, 95], fill=(70, 54, 40, 255))
for i in range(7):                                                            # pine: stacked triangles
    y = 8 + i * 10; w = 6 + i * 4
    col = tuple(int(c * rnd.uniform(0.85, 1.1)) for c in (40, 74, 46)) + (255,)
    d.polygon([(32, y), (32 - w, y + 16), (32 + w, y + 16)], fill=col)
save(im, 'tree_pine')

# blob shadow
s = 32
y, x = np.mgrid[0:s, 0:s] / (s - 1) * 2 - 1
alpha = np.clip(1 - np.sqrt(x * x + y * y), 0, 1) ** 1.5 * 180
im = np.zeros((s, s, 4), np.uint8); im[..., 3] = alpha.astype(np.uint8)
save(Image.fromarray(im), 'blob_shadow')
print('ok')
