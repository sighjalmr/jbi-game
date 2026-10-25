"""Retro (PS2/PS3 era, Tony Hawk's American Wasteland style) versions of the JBI textures, plus the tree atlas.

Usage: python3 gen_retro.py <out_dir>

Runs gen_facades.py and gen_ground.py into a temp folder, then shrinks every texture to a small power of two,
pushes saturation and contrast up and flattens the fine noise, so surfaces read as clean painted colour from afar.
Also draws tree_atlas_BC.png (RGBA, alpha = cutout): pine bark | birch bark on the bottom row,
pine needles | birch leaves on the top row, 256 px quadrants. Tools/map/build_trees.py maps its UVs onto it.
"""
import os, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from scipy.ndimage import gaussian_filter

OUT = sys.argv[1] if len(sys.argv) > 1 else 'textures'
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(2005)

# longest side in px after shrinking; facades keep enough for crisp windows
SIZE = {'panel': 512, 'khrush': 512, 'public': 512, 'industrial': 512, 'garage': 256, 'roof': 128, 'trim': 128,
        'asphalt': 256, 'paving': 256, 'ballast': 128, 'grass': 256, 'dirt': 256, 'forest': 256}
SATURATION = {'grass': 1.5, 'forest': 1.4, 'garage': 1.4, 'public': 1.35}

src = tempfile.mkdtemp()
for gen in ('gen_facades.py', 'gen_ground.py'):
    subprocess.run([sys.executable, os.path.join(HERE, gen), src], check=True, stdout=subprocess.DEVNULL)

for f in sorted(os.listdir(src)):
    name, suffix = f[:-4].rsplit('_', 1)
    if name not in SIZE:
        continue
    im = Image.open(os.path.join(src, f))
    s = SIZE[name] / max(im.size)
    im = im.resize((max(4, round(im.width * s)), max(4, round(im.height * s))), Image.LANCZOS)
    if suffix == 'BC':
        im = im.filter(ImageFilter.SMOOTH)
        im = ImageEnhance.Color(im).enhance(SATURATION.get(name, 1.25))
        im = ImageEnhance.Contrast(im).enhance(1.12)
        im = ImageEnhance.Brightness(im).enhance(1.05)
    elif suffix == 'N':   # softer bumps: shapes stay readable, the pores go
        a = (np.asarray(im, float) / 127.5 - 1.0)
        a[..., :2] *= 0.5
        a /= np.linalg.norm(a, axis=2, keepdims=True)
        im = Image.fromarray(((a * 0.5 + 0.5) * 255).astype(np.uint8))
    im.save(os.path.join(OUT, f))

# ---------------------------------------------------------------- tree atlas
Q = 256


def noise(shape, sigma, amp=1.0):
    n = gaussian_filter(rng.standard_normal(shape), sigma, mode='wrap')
    return n / (n.std() + 1e-9) * amp


def bark_pine():
    c = np.ones((Q, Q, 3)) * np.array([128, 74, 46], float)
    stripes = noise((Q, Q), (12, 1.5))              # long vertical plates
    c *= (1 + 0.18 * stripes)[..., None]
    c[np.abs(noise((Q, Q), (6, 1))) < 0.12] *= 0.55  # dark cracks between plates
    return np.dstack([c, np.full((Q, Q), 255.0)])


def bark_birch():
    c = np.ones((Q, Q, 3)) * np.array([232, 228, 218], float) * (1 + 0.04 * noise((Q, Q), 3))[..., None]
    for _ in range(26):                              # black lenticels: short horizontal dashes
        y, x = rng.integers(0, Q, 2)
        w, h = rng.integers(10, 45), rng.integers(2, 6)
        xs = (np.arange(x, x + w) % Q)
        c[y:y + h, xs] = np.array([40, 38, 36])
    return np.dstack([c, np.full((Q, Q), 255.0)])


def needles():
    """Pine crown skirt: dark green, clumps of needles, jagged fringe at the bottom (v = 0 at the cone base)."""
    c = np.ones((Q, Q, 3)) * np.array([38, 92, 44], float)
    c *= (1 + 0.25 * noise((Q, Q), (5, 1.2)))[..., None]
    c += (np.clip(noise((Q, Q), (3, 1)), 0, None) * 18)[..., None] * np.array([0.6, 1.0, 0.4])
    a = np.full((Q, Q), 255.0)
    teeth = (np.sin(np.arange(Q) / Q * 2 * np.pi * 14) * 0.5 + 0.5) * 34 + rng.uniform(0, 12, Q)
    rows = np.arange(Q)[:, None]
    a[rows >= Q - teeth[None, :]] = 0                # fringe at the bottom rows of the image
    c[rows >= Q - teeth[None, :] - 10] *= 0.75       # darker underside before the fringe
    return np.dstack([c, a])


def leaves():
    """Birch foliage card: clusters of small round leaves, transparent between them."""
    c = np.zeros((Q, Q, 3)); a = np.zeros((Q, Q))
    yy, xx = np.mgrid[0:Q, 0:Q]
    for _ in range(420):
        cx, cy = rng.normal(Q / 2, Q / 5, 2)
        r = rng.uniform(4, 9)
        m = (xx - cx) ** 2 + (yy - cy) ** 2 < r * r
        col = np.array([95, 150, 45]) * rng.uniform(0.75, 1.15) + np.array([20, 10, 0]) * rng.random()
        if rng.random() < 0.12:                      # a few autumn-yellow leaves
            col = np.array([200, 175, 50]) * rng.uniform(0.85, 1.1)
        c[m] = col; a[m] = 255
    return np.dstack([c, a])


atlas = np.zeros((2 * Q, 2 * Q, 4))
atlas[Q:, :Q] = bark_pine()          # bottom-left  (image rows Q..2Q = UV v 0..0.5)
atlas[Q:, Q:] = bark_birch()         # bottom-right
atlas[:Q, :Q] = needles()            # top-left
atlas[:Q, Q:] = leaves()             # top-right
Image.fromarray(np.clip(atlas, 0, 255).astype(np.uint8), 'RGBA').save(os.path.join(OUT, 'tree_atlas_BC.png'))
print('ok', len(os.listdir(OUT)), 'files')
