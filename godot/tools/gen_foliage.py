"""Leaf, needle and bark textures for the procedural trees (godot/textures/foliage/).

    python godot/tools/gen_foliage.py
"""
import os, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(__file__), '..', 'textures', 'foliage')
os.makedirs(OUT, exist_ok=True)
rnd = random.Random(5)
S = 512

def leaves(name, base, count, leaf_len, leaf_w, droop):
    """A cluster of small leaves on twigs, alpha cut-out. Twig root at the bottom centre."""
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    twigs = []
    for i in range(9):                          # twigs fanning out from the bottom
        a = math.radians(rnd.uniform(-70, 70))
        L = rnd.uniform(0.55, 0.9) * S
        x0, y0 = S / 2, S * 0.98
        pts = []
        for t in np.linspace(0, 1, 12):
            x = x0 + math.sin(a) * L * t
            y = y0 - math.cos(a) * L * t + droop * S * t * t
            pts.append((x, y))
        twigs.append(pts)
        d.line(pts, fill=(70, 58, 44, 255), width=3)
    for _ in range(count):
        tw = rnd.choice(twigs)
        x, y = tw[rnd.randrange(3, 12)]
        x += rnd.gauss(0, 14); y += rnd.gauss(0, 14)
        a = rnd.uniform(0, math.tau)
        shade = rnd.uniform(0.65, 1.2)
        col = tuple(int(min(255, c * shade)) for c in base) + (255,)
        l, w = leaf_len * rnd.uniform(0.7, 1.2), leaf_w * rnd.uniform(0.7, 1.2)
        poly = []
        for k in range(10):
            t = k / 9 * math.pi
            px_, py_ = math.cos(t) * l, math.sin(t) * w * math.sin(t)
            poly.append((px_, py_))
        poly += [(p[0], -p[1]) for p in reversed(poly)]
        poly = [(x + px_ * math.cos(a) - py_ * math.sin(a), y + px_ * math.sin(a) + py_ * math.cos(a)) for px_, py_ in poly]
        d.polygon(poly, fill=col)
    # premultiply-safe edge: bleed colour into transparent pixels so mipmaps don't go dark
    rgb = im.convert('RGB').filter(ImageFilter.MaxFilter(5))
    out = Image.merge('RGBA', (*rgb.split(), im.split()[3]))
    out.save(f'{OUT}/{name}.png')

leaves('leaves_birch', (86, 128, 44), 1100, 16, 9, 0.08)
leaves('leaves_broad', (64, 104, 40), 900, 22, 13, 0.06)

# pine: needle bundles along a branch
im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
for i in range(7):
    y = S * (0.15 + i * 0.12)
    d.line([(S * 0.05, S * 0.5), (S * 0.95, y)], fill=(80, 60, 44, 255), width=4)
    for t in np.linspace(0.1, 1, 40):
        bx, by = S * 0.05 + (S * 0.9) * t, S * 0.5 + (y - S * 0.5) * t
        for _ in range(14):
            a = rnd.uniform(0, math.tau); L = rnd.uniform(16, 34)
            col = tuple(int(c * rnd.uniform(0.7, 1.15)) for c in (38, 72, 42)) + (255,)
            d.line([(bx, by), (bx + math.cos(a) * L, by + math.sin(a) * L)], fill=col, width=3)
rgb = im.convert('RGB').filter(ImageFilter.MaxFilter(5))
Image.merge('RGBA', (*rgb.split(), im.split()[3])).rotate(90).save(f'{OUT}/needles.png')   # branch root at the bottom

def bark(name, base, marks):
    r = np.random.default_rng(len(name))
    a = np.ones((256, 128, 3), np.float32) * np.array(base, np.float32)
    n = r.normal(0, 1, (256, 128))
    from PIL import Image as I
    streak = np.array(I.fromarray(((n - n.min()) / np.ptp(n) * 255).astype(np.uint8)).resize((16, 256)).resize((128, 256), I.BICUBIC)) / 255 - 0.5
    a += streak[..., None] * 40 + r.normal(0, 8, (256, 128, 1))
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if marks:      # birch: black horizontal lenticels
        d = ImageDraw.Draw(im)
        for _ in range(60):
            x, y = rnd.randrange(128), rnd.randrange(256)
            w = rnd.randint(6, 30)
            d.rectangle([x, y, x + w, y + rnd.randint(2, 5)], fill=(40, 38, 36))
            d.rectangle([x - 128, y, x + w - 128, y + 3], fill=(40, 38, 36))
    im.save(f'{OUT}/{name}.jpg', quality=90)

bark('bark_birch', (222, 218, 206), True)
bark('bark_pine', (120, 78, 52), False)
print('ok')

# grass clump card: blades rising from the bottom edge
W, H = 256, 128
im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
for _ in range(220):
    x = rnd.uniform(4, W - 4); h = rnd.uniform(0.35, 1.0) * H; lean = rnd.uniform(-30, 30)
    shade = rnd.uniform(0.6, 1.15)
    base = rnd.choice([(84, 112, 44), (104, 124, 52), (120, 120, 60), (70, 98, 40)])
    col = tuple(int(min(255, c * shade)) for c in base) + (255,)
    w = rnd.uniform(2, 4)
    d.polygon([(x - w, H), (x + w, H), (x + lean, H - h)], fill=col)
rgb = im.convert('RGB').filter(ImageFilter.MaxFilter(5))
Image.merge('RGBA', (*rgb.split(), im.split()[3])).save(f'{OUT}/grass_clump.png')
print('grass ok')
