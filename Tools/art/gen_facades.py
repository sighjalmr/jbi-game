"""Procedural facade and roof textures for the ЖБИ district buildings.

Usage: python3 gen_facades.py <out_dir>

Each facade texture covers a fixed real-world size (FACADES[...]['size_m']); build_jbi.py writes wall UVs in those
units, so windows land on real floor heights. Output per type: <type>_BC.png (base colour), <type>_N.png (normal,
DirectX/Unreal green-down), <type>_R.png (roughness).
"""
import sys, os
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, sobel

OUT = sys.argv[1] if len(sys.argv) > 1 else 'textures'
os.makedirs(OUT, exist_ok=True)
PPM = 128  # pixels per metre
rng = np.random.default_rng(1977)

# metres: width, height of one texture tile, and which generator draws it
FACADES = {
    'panel':      {'size_m': (12.8, 8.4)},   # 9-16 storey panel blocks (series 121, 1-468): 4 panels x 3 floors
    'khrush':     {'size_m': (12.0, 8.4)},   # 5 storey silicate-brick khrushchyovka
    'public':     {'size_m': (12.0, 7.2)},   # schools, kindergartens, clinics: red brick, big windows
    'garage':     {'size_m': (9.6, 3.0)},    # garage rows: block wall + metal gates
    'industrial': {'size_m': (12.0, 6.0)},   # ЖБИ plant halls: corrugated sheet + ribbon windows
    'roof':       {'size_m': (4.0, 4.0)},    # flat bitumen roof with gravel
    'trim':       {'size_m': (4.0, 4.0)},    # plinths, parapets, lift machine rooms: weathered cast concrete
}

def noise(shape, sigma, amp=1.0):
    n = gaussian_filter(rng.standard_normal(shape), sigma, mode='wrap')
    return n / (n.std() + 1e-9) * amp

def canvas(t):
    w, h = FACADES[t]['size_m']
    return int(round(h * PPM)), int(round(w * PPM))

def px(m):
    return int(round(m * PPM))

def rect(a, x0, y0, x1, y1, v):
    a[px(y0):px(y1), px(x0):px(x1)] = v

def window(col, hgt, rough, x, y, w, h, frame=(225, 225, 220), glass=None, sill=True, depth=0.6):
    """Window with PVC frame, 2 panes, random curtain. x,y = top-left in metres from tile top-left."""
    f = 0.07
    rect(col, x, y, x + w, y + h, frame); rect(hgt, x, y, x + w, y + h, -0.15); rect(rough, x, y, x + w, y + h, 0.35)
    g = glass if glass is not None else np.array([55, 66, 74]) + rng.integers(-8, 8, 3)
    for gx0, gx1 in [(x + f, x + w / 2 - f / 2), (x + w / 2 + f / 2, x + w - f)]:
        rh = px(y + h - f) - px(y + f); rw = px(gx1) - px(gx0)
        grad = np.linspace(1.25, 0.75, rh)[:, None, None] * np.ones((1, rw, 1))
        pane = np.clip(g * grad, 0, 255)
        if rng.random() < 0.55:  # curtain / blind behind glass
            cc = np.array(rng.choice([[200, 190, 160], [230, 225, 215], [150, 60, 50], [120, 140, 110], [180, 170, 200]]))
            cw = int(rw * rng.uniform(0.3, 1.0))
            side = rng.random() < 0.5
            sl = slice(0, cw) if side else slice(rw - cw, rw)
            pane[:, sl] = pane[:, sl] * 0.65 + cc * 0.25
        col[px(y + f):px(y + f) + rh, px(gx0):px(gx0) + rw] = pane
        hgt[px(y + f):px(y + f) + rh, px(gx0):px(gx0) + rw] = -depth
        rough[px(y + f):px(y + f) + rh, px(gx0):px(gx0) + rw] = 0.05
    if sill:
        rect(col, x - 0.05, y + h, x + w + 0.05, y + h + 0.06, (170, 172, 175)); rect(hgt, x - 0.05, y + h, x + w + 0.05, y + h + 0.06, 0.1)
        # rain streak under the sill
        sx0, sx1 = px(x), px(x + w); sy0 = px(y + h + 0.06)
        L = min(px(rng.uniform(0.4, 1.2)), col.shape[0] - sy0)
        if L > 0:
            fade = np.linspace(0.82, 1.0, L)[:, None, None]
            col[sy0:sy0 + L, sx0:sx1] = col[sy0:sy0 + L, sx0:sx1] * fade

def grime(col, strength=0.12):
    h, w, _ = col.shape
    streaks = gaussian_filter(rng.standard_normal((h // 8, w)), (h / 16, 6), mode='wrap')
    streaks = np.array(Image.fromarray(((streaks - streaks.min()) / np.ptp(streaks) * 255).astype(np.uint8)).resize((w, h)))[..., None] / 255.0
    blotch = (noise((h, w), 40) * 0.5 + noise((h, w), 6) * 0.2)[..., None]
    return np.clip(col * (1 - strength * streaks) * (1 + 0.05 * blotch), 0, 255)

def save(t, col, hgt, rough):
    Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).save(f'{OUT}/{t}_BC.png')
    hb = gaussian_filter(hgt, 1.0, mode='wrap') * 6.0
    nx, ny = -sobel(hb, 1, mode='wrap'), sobel(hb, 0, mode='wrap')
    n = np.dstack([nx, ny, np.ones_like(hb) * 8.0]); n /= np.linalg.norm(n, axis=2, keepdims=True)
    Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8)).save(f'{OUT}/{t}_N.png')
    Image.fromarray((np.clip(rough, 0, 1) * 255).astype(np.uint8)).save(f'{OUT}/{t}_R.png')

def base(t, color, var=8, rough_v=0.85):
    H, W = canvas(t)
    col = np.ones((H, W, 3)) * np.array(color, float) + noise((H, W), 2, var)[..., None] + noise((H, W), 30, var)[..., None]
    return col, noise((H, W), 1, 0.05), np.full((H, W), rough_v) + noise((H, W), 8, 0.04)

def bricks(col, hgt, x0, y0, x1, y1, c, mortar, bw=0.25, bh=0.077):
    """Stretcher bond; c = brick colour, randomised per brick."""
    for j, y in enumerate(np.arange(y0, y1, bh)):
        off = (j % 2) * bw / 2
        for x in np.arange(x0 - off, x1, bw):
            cc = np.array(c) * rng.uniform(0.88, 1.08) + rng.integers(-6, 6, 3)
            xa, xb = max(x, x0), min(x + bw - 0.012, x1)
            if xb > xa:
                rect(col, xa, y, xb, min(y + bh - 0.012, y1), cc)
    # mortar is whatever was there: set it first
    return col

# ------------------------------------------------------------------ panel block (series 121 / 1-468)
col, hgt, rough = base('panel', (196, 192, 182), 7)
pw, fh = 3.2, 2.8
for i in range(4):
    for k in range(3):
        x, y = i * pw, k * fh
        tint = rng.uniform(0.94, 1.05)
        col[px(y):px(y + fh), px(x):px(x + pw)] *= tint
        # panel seams, sealed with dark mastic (very typical of Ekb panel blocks)
        rect(col, x, y, x + 0.035, y + fh, (95, 92, 88)); rect(hgt, x, y, x + 0.035, y + fh, -0.3)
        rect(col, x, y, x + pw, y + 0.035, (95, 92, 88)); rect(hgt, x, y, x + pw, y + 0.035, -0.3)
        if i == 1:  # loggia: concrete parapet, mostly glazed by residents
            rect(col, x + 0.15, y + 1.55, x + pw - 0.15, y + 2.55, (175, 172, 165))
            rect(hgt, x + 0.15, y + 1.55, x + pw - 0.15, y + 2.55, 0.4)
            if rng.random() < 0.7:
                window(col, hgt, rough, x + 0.2, y + 0.55, pw - 0.4, 1.0, frame=(235, 235, 230), sill=False, depth=0.3)
            else:
                rect(col, x + 0.2, y + 0.55, x + pw - 0.2, y + 1.55, (60, 58, 55)); rect(hgt, x + 0.2, y + 0.55, x + pw - 0.2, y + 1.55, -0.9)
        else:
            frame = (235, 235, 230) if rng.random() < 0.75 else (120, 85, 55)  # new PVC vs old wooden frames
            window(col, hgt, rough, x + 0.85, y + 0.75, 1.5, 1.45, frame=frame)
col = grime(col, 0.14)
save('panel', col, hgt, rough)

# ------------------------------------------------------------------ khrushchyovka, white silicate brick
col, hgt, rough = base('khrush', (150, 148, 142), 4)
bricks(col, hgt, 0, 0, 12.0, 8.4, (214, 210, 200), None)
for i in range(4):
    for k in range(3):
        x, y = i * 3.0, k * 2.8
        frame = (235, 235, 230) if rng.random() < 0.65 else (130, 95, 60)
        window(col, hgt, rough, x + 0.8, y + 0.8, 1.4, 1.45, frame=frame)
        rect(col, x + 0.7, y + 0.7, x + 2.3, y + 0.78, (190, 186, 178))  # brick lintel
col = grime(col, 0.16)
save('khrush', col, hgt, rough)

# ------------------------------------------------------------------ public buildings, red brick
col, hgt, rough = base('public', (140, 120, 110), 4)
bricks(col, hgt, 0, 0, 12.0, 7.2, (150, 72, 52), None)
for i in range(4):
    for k in range(2):
        x, y = i * 3.0, k * 3.6
        window(col, hgt, rough, x + 0.4, y + 0.9, 2.2, 1.9, frame=(235, 235, 230))
    rect(col, i * 3.0, 3.45, i * 3.0 + 3.0, 3.6, (200, 196, 188))  # concrete floor band
col = grime(col, 0.1)
save('public', col, hgt, rough)

# ------------------------------------------------------------------ garages: concrete block + painted steel gates
col, hgt, rough = base('garage', (165, 160, 150), 8)
for i in range(3):
    x = i * 3.2
    rect(col, x, 0, x + 0.04, 3.0, (110, 106, 100))
    gc = np.array(rng.choice([[70, 90, 70], [80, 80, 90], [110, 60, 40], [60, 75, 100], [140, 130, 110]]))
    rect(col, x + 0.35, 0.65, x + 2.85, 3.0, gc); rect(hgt, x + 0.35, 0.65, x + 2.85, 3.0, -0.2); rect(rough, x + 0.35, 0.65, x + 2.85, 3.0, 0.55)
    rect(col, x + 1.58, 0.65, x + 1.62, 3.0, gc * 0.6)
    rust = np.clip(noise((px(2.35), px(2.5)), 6, 1) - 0.6, 0, 1)[..., None]
    sl = (slice(px(0.65), px(0.65) + px(2.35)), slice(px(x + 0.35), px(x + 0.35) + px(2.5)))
    col[sl] = col[sl] * (1 - rust * 0.6) + np.array([120, 60, 30]) * rust * 0.6
col = grime(col, 0.2)
save('garage', col, hgt, rough)

# ------------------------------------------------------------------ industrial hall: corrugated sheet + ribbon glazing
col, hgt, rough = base('industrial', (170, 175, 178), 5, 0.6)
H, W = canvas('industrial')
ribs = (np.sin(np.arange(W) / px(0.2) * 2 * np.pi) > 0.3).astype(float)
hgt += ribs[None, :] * 0.25
col *= (0.95 + 0.05 * ribs[None, :, None])
rect(col, 0, 1.6, 12.0, 2.8, (90, 100, 105)); rect(hgt, 0, 1.6, 12.0, 2.8, -0.2)
for i in range(10):
    window(col, hgt, rough, i * 1.2 + 0.05, 1.65, 1.1, 1.1, frame=(150, 155, 160), sill=False, depth=0.3)
rect(col, 0, 5.0, 12.0, 6.0, (120, 118, 112)); rect(hgt, 0, 5.0, 12.0, 6.0, 0.1)  # concrete plinth
col = grime(col, 0.22)
save('industrial', col, hgt, rough)

# ------------------------------------------------------------------ trim: cast concrete, formwork joints, damp stains
col, hgt, rough = base('trim', (150, 147, 140), 9, 0.9)
H, W = canvas('trim')
for x in np.arange(0, 4.0, 1.0):  # formwork board joints
    rect(col, x, 0, x + 0.02, 4.0, (120, 117, 111)); rect(hgt, x, 0, x + 0.02, 4.0, -0.2)
pores = rng.random((H, W)) < 0.03
col[pores] *= 0.75; hgt[pores] -= 0.3
damp = np.clip(noise((H, W), 25, 0.5), 0, 1)[..., None]  # damp patches (no gradient: the tile must wrap)
col = col * (1 - 0.15 * damp)
col = grime(col, 0.18)
save('trim', col, hgt, rough)

# ------------------------------------------------------------------ flat roof: bitumen with gravel
col, hgt, rough = base('roof', (62, 60, 58), 10, 0.9)
H, W = canvas('roof')
g = rng.random((H, W)) < 0.08
col[g] = col[g] * 0.5 + np.array([150, 145, 135]) * 0.5
hgt[g] += 0.3
for y in np.arange(0, 4.0, 1.0):  # roll seams of the bitumen membrane
    rect(col, 0, y, 4.0, y + 0.05, (45, 44, 42)); rect(hgt, 0, y, 4.0, y + 0.05, 0.25)
save('roof', col, hgt, rough)

print('ok', sorted(os.listdir(OUT)))
