"""Procedural, seamless ground textures (4x4 m tiles): roads, paths, rail ballast and landscape layers.

Usage: python3 gen_ground.py <out_dir>
Output per surface: <name>_BC.png, <name>_N.png, <name>_R.png (same convention as gen_facades.py).
"""
import sys, os
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, sobel

OUT = sys.argv[1] if len(sys.argv) > 1 else 'textures'
os.makedirs(OUT, exist_ok=True)
N = 1024  # px per 4 m tile
rng = np.random.default_rng(1957)

def noise(sigma, amp=1.0):
    n = gaussian_filter(rng.standard_normal((N, N)), sigma, mode='wrap')
    return n / (n.std() + 1e-9) * amp

def save(name, col, hgt, rough, nstr=4.0):
    Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).save(f'{OUT}/{name}_BC.png')
    hb = gaussian_filter(hgt, 1.0, mode='wrap') * nstr
    n = np.dstack([-sobel(hb, 1, mode='wrap'), sobel(hb, 0, mode='wrap'), np.full(hb.shape, 8.0)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8)).save(f'{OUT}/{name}_N.png')
    Image.fromarray((np.clip(rough, 0, 1) * 255).astype(np.uint8)).save(f'{OUT}/{name}_R.png')

def mix(a, b, t):
    t = np.clip(t, 0, 1)[..., None]
    return a * (1 - t) + b * t

def flat(c):
    return np.ones((N, N, 3)) * np.array(c, float)

def specks(p, size_sigma=0.0):
    s = (rng.random((N, N)) < p).astype(float)
    return gaussian_filter(s, size_sigma, mode='wrap') if size_sigma else s

# old worn asphalt, patched, with cracks
grain = noise(0.8, 1) + noise(2, 0.6)
col = flat((72, 72, 74)) + grain[..., None] * 9
stones = specks(0.05, 0.6); col = mix(col, flat((120, 118, 112)), stones * 3)
col = mix(col, flat((48, 48, 50)), (noise(60) > 1.1) * 0.6)          # fresh patch repairs
crack = np.abs(noise(25)) < 0.03
col[crack] *= 0.55
col *= (1 + noise(80, 0.05))[..., None]
save('asphalt', col, grain * 0.3 + stones * 0.4 - crack * 1.0, 0.8 + noise(20, 0.05))

# concrete slabs (sidewalks and yards: 1x1 m tiles, typical Soviet paving)
col = flat((150, 147, 140)) + noise(1, 6)[..., None] + noise(40, 10)[..., None]
hgt = noise(1, 0.15)
slab = N // 4
for i in range(4):
    for j in range(4):
        sl = (slice(i * slab, (i + 1) * slab), slice(j * slab, (j + 1) * slab))
        col[sl] *= rng.uniform(0.9, 1.08)
        hgt[sl] += rng.uniform(-0.3, 0.3)
joint = np.zeros((N, N), bool)
for k in range(4):
    joint[k * slab:k * slab + 5, :] = True; joint[:, k * slab:k * slab + 5] = True
col[joint] = col[joint] * 0.55 + np.array([60, 70, 45]) * 0.35  # moss in the joints
hgt[joint] -= 1.0
save('paving', col, hgt, 0.85 + noise(10, 0.04))

# rail ballast: crushed granite
pebbles = gaussian_filter(rng.random((N, N)), 2.5, mode='wrap')
pebbles = (pebbles - pebbles.min()) / np.ptp(pebbles)
col = mix(flat((95, 90, 85)), flat((150, 145, 140)), pebbles) + noise(1, 10)[..., None]
col = mix(col, flat((90, 60, 40)), (noise(30) > 0.8) * 0.4)  # rust stains
save('ballast', col, pebbles * 2.0, 0.9 + noise(5, 0.03), 6.0)

# lawn grass: Urals autumn, green with straw patches and bare spots
blades = noise(0.7, 1) + noise(1.5, 0.5)
dry = np.clip(noise(50, 0.6) + 0.1, 0, 1)
col = mix(flat((70, 95, 45)), flat((140, 130, 70)), dry) * (1 + blades[..., None] * 0.18)
col = mix(col, flat((95, 80, 60)), np.clip(noise(30) - 1.4, 0, 1))
save('grass', col, blades * 0.5, 0.95 + noise(10, 0.02))

# bare dirt and gravel (yards, construction, industrial)
col = flat((110, 95, 78)) + noise(1, 8)[..., None] + noise(25, 12)[..., None]
grav = specks(0.04, 0.8); col = mix(col, flat((150, 140, 125)), grav * 3)
puddle = np.clip(noise(70) - 1.3, 0, 1)
col = mix(col, flat((70, 60, 50)), puddle)
save('dirt', col, noise(2, 0.4) + grav * 0.6 - puddle, 0.9 - puddle * 0.7)

# forest floor: birch and pine litter, typical for the Shartash forest park edge
col = mix(flat((80, 70, 45)), flat((130, 100, 50)), np.clip(noise(4) * 0.5 + 0.5, 0, 1))
needles = specks(0.02, 0.5); col = mix(col, flat((150, 110, 60)), needles * 3)
leaves = np.clip(noise(3) - 1.0, 0, 1); col = mix(col, flat((190, 150, 50)), leaves)
moss = np.clip(noise(40) - 0.6, 0, 1); col = mix(col, flat((65, 85, 40)), moss * 0.7)
save('forest', col, noise(2, 0.6) + leaves, 0.9 + noise(10, 0.03))

print('ok', sorted(os.listdir(OUT)))
