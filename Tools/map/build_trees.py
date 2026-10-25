"""Low-poly retro trees (PS2-era style) for the ЖБИ district: 4 pines and 4 birches, one atlas material.

Usage: python3 build_trees.py <MapData dir>

Writes MapData/meshes/tree_<pine|birch>_<A-D>.glb (metres, same glTF frame as build_jbi.py). Each tree is a
6-sided trunk and either stacked needle cones (pine) or crossed leaf cards (birch), ~150-300 triangles.
UVs point into tree_atlas_BC.png from Tools/art/gen_retro.py: v 0-0.5 = bark (pine left, birch right),
v 0.5-1 = foliage (needles left, leaves right). Pivot at the trunk base; plant_trees.py scales them per tree.
"""
import os, sys
import numpy as np
import trimesh

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MapData'
ZUP_TO_YUP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float)
PAD = 0.01


class Mesh:
    def __init__(self):
        self.V, self.F, self.UV = [], [], []

    def tri(self, pts, uvs):
        i = len(self.V)
        self.V += pts; self.UV += uvs; self.F.append([i, i + 1, i + 2])

    def quad(self, pts, uvs):
        i = len(self.V)
        self.V += pts; self.UV += uvs; self.F += [[i, i + 1, i + 2], [i, i + 2, i + 3]]


def quadrant(col, row, u, v):
    """Map local (u, v) in 0-1 into atlas quadrant col (0 left, 1 right), row (0 bark, 1 foliage)."""
    return [col * 0.5 + PAD + u * (0.5 - 2 * PAD), row * 0.5 + PAD + v * (0.5 - 2 * PAD)]


def trunk(m, col, h, r0, r1, lean, segments=3, sides=6):
    """Tapered trunk in stacked segments; each segment maps the whole bark quadrant once."""
    for s in range(segments):
        z0, z1 = h * s / segments, h * (s + 1) / segments
        ra, rb = r0 + (r1 - r0) * s / segments, r0 + (r1 - r0) * (s + 1) / segments
        oa, ob = lean * z0 / h, lean * z1 / h
        for k in range(sides):
            a0, a1 = 2 * np.pi * k / sides, 2 * np.pi * (k + 1) / sides
            p = lambda a, r, z, o: [np.cos(a) * r + o[0], np.sin(a) * r + o[1], z]
            m.quad([p(a0, ra, z0, oa), p(a1, ra, z0, oa), p(a1, rb, z1, ob), p(a0, rb, z1, ob)],
                   [quadrant(col, 0, k / sides, 0), quadrant(col, 0, (k + 1) / sides, 0),
                    quadrant(col, 0, (k + 1) / sides, 1), quadrant(col, 0, k / sides, 1)])


def pine(rng):
    m = Mesh()
    h = rng.uniform(16, 22)
    lean = rng.normal(0, 0.25, 2)
    trunk(m, 0, h, rng.uniform(0.22, 0.3), 0.06, lean)
    tiers = int(rng.integers(4, 6))
    base = h * rng.uniform(0.42, 0.55)
    for t in range(tiers):
        f = t / tiers
        z0 = base + (h - base) * f
        z1 = min(h + 1.0, z0 + (h - base) / tiers * 1.9)
        r = (2.6 - 1.8 * f) * rng.uniform(0.85, 1.15)
        o = lean * z0 / h
        apex = [lean[0] * z1 / h, lean[1] * z1 / h, z1]
        sides = 7
        rot = rng.uniform(0, 2 * np.pi)
        for k in range(sides):
            a0, a1 = rot + 2 * np.pi * k / sides, rot + 2 * np.pi * (k + 1) / sides
            j = rng.uniform(0.85, 1.15, 2)
            p0 = [o[0] + np.cos(a0) * r * j[0], o[1] + np.sin(a0) * r * j[0], z0 - rng.uniform(0, 0.6)]
            p1 = [o[0] + np.cos(a1) * r * j[1], o[1] + np.sin(a1) * r * j[1], z0 - rng.uniform(0, 0.6)]
            m.tri([p0, p1, apex], [quadrant(0, 1, 0, 0), quadrant(0, 1, 1, 0), quadrant(0, 1, 0.5, 1)])
    return m


def birch(rng):
    m = Mesh()
    h = rng.uniform(13, 17)
    lean = rng.normal(0, 0.5, 2)
    trunk(m, 1, h * 0.85, rng.uniform(0.15, 0.2), 0.05, lean, segments=4)
    top = np.array([lean[0] * 0.85, lean[1] * 0.85, h * 0.85])
    for _ in range(int(rng.integers(9, 13))):     # leaf cards around an egg-shaped crown
        c = top * np.array([1, 1, 0]) + np.array([0, 0, h * rng.uniform(0.45, 0.92)]) \
            + np.r_[rng.normal(0, 1.4, 2), 0]
        s = rng.uniform(2.6, 4.2)
        yaw, tilt = rng.uniform(0, np.pi), rng.uniform(-0.5, 0.5)
        d = np.array([np.cos(yaw), np.sin(yaw), 0]) * s / 2
        up = np.array([-np.sin(yaw) * np.sin(tilt), np.cos(yaw) * np.sin(tilt), np.cos(tilt)]) * s / 2
        m.quad([(c - d - up).tolist(), (c + d - up).tolist(), (c + d + up).tolist(), (c - d + up).tolist()],
               [quadrant(1, 1, 0, 0), quadrant(1, 1, 1, 0), quadrant(1, 1, 1, 1), quadrant(1, 1, 0, 1)])
    return m


os.makedirs(f'{MAP}/meshes', exist_ok=True)
for species, fn, seed in (('pine', pine, 11), ('birch', birch, 23)):
    rng = np.random.default_rng(seed)
    for v in 'ABCD':
        t = fn(rng)
        mesh = trimesh.Trimesh(np.array(t.V), np.array(t.F), process=False)
        mesh.visual = trimesh.visual.TextureVisuals(uv=np.array(t.UV),
                                                    material=trimesh.visual.material.PBRMaterial(name='tree'))
        mesh.apply_transform(ZUP_TO_YUP)
        mesh.export(f'{MAP}/meshes/tree_{species}_{v}.glb')
        print(species, v, len(mesh.faces), 'tris')
