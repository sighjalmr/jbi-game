"""Rebuild the building meshes from MapData/geojson/buildings.geojson with more detail than build_jbi.py's boxes.

Usage: python3 build_buildings.py <MapData dir>

Adds to every building: a concrete plinth (ground floor windows sit above it, like real Soviet blocks), a parapet
around flat roofs, lift machine rooms on tall blocks, a per-building colour tint in the vertex colours and a random
facade texture offset so neighbouring blocks don't look stamped out. Writes MapData/meshes/bld_<surface>_<kx>_<ky>.glb
in the same 1 km tiles and frame as build_jbi.py; trim parts (plinth, parapet, machine rooms) go to bld_trim_*.
"""
import sys, os, json, zlib
import numpy as np
import shapely
from shapely.geometry import shape, Polygon, MultiPolygon
import trimesh

MAP = sys.argv[1] if len(sys.argv) > 1 else 'MapData'
HALF, TILE = 2016.0, 1008.0
# Facade texture tile sizes in metres, must match Tools/art/gen_facades.py.
FACADE_TILE = {'panel': (12.8, 8.4), 'khrush': (12.0, 8.4), 'public': (12.0, 7.2), 'garage': (9.6, 3.0),
               'industrial': (12.0, 6.0)}
ROOF_TILE, TRIM_TILE = 4.0, 4.0
PLINTH = {'panel': 1.0, 'khrush': 0.8, 'public': 0.6}           # m above the lowest ground point
PARAPET = {'panel': 0.6, 'khrush': 0.5, 'public': 0.6, 'industrial': 0.5}
PARAPET_W = 0.3
# Per-building tints (multiplied with the facade texture). Panel blocks in ЖБИ: grey, beige, pale blue, pale pink.
TINTS = {
    'panel': [(1.0, 1.0, 1.0), (1.04, 0.99, 0.9), (0.92, 0.97, 1.04), (1.04, 0.95, 0.93), (1.02, 1.01, 0.88), (0.9, 0.9, 0.9)],
    'khrush': [(1.0, 1.0, 1.0), (1.03, 1.0, 0.94), (0.95, 0.95, 0.95)],
    'public': [(1.0, 1.0, 1.0), (1.05, 0.98, 0.95), (0.92, 0.92, 0.92)],
    'garage': [(1.0, 1.0, 1.0), (0.9, 0.9, 0.88), (1.03, 1.0, 0.95)],
    'industrial': [(1.0, 1.0, 1.0), (0.92, 0.95, 0.98), (1.02, 0.98, 0.92)],
}
ZUP_TO_YUP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float)


class Part:
    """Vertices, faces, UVs and vertex colours of one output mesh."""
    def __init__(self):
        self.V, self.F, self.UV, self.C = [], [], [], []

    def quad(self, pts, uvs, col):
        i = len(self.V)
        self.V += pts; self.UV += uvs; self.C += [col] * 4
        self.F += [[i, i + 1, i + 2], [i, i + 2, i + 3]]

    def cap(self, poly, z, uv_scale, col):
        try:
            v, f = trimesh.creation.triangulate_polygon(poly, engine='earcut')
        except Exception:
            return
        a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
        flip = ((b - a)[:, 0] * (c - a)[:, 1] - (b - a)[:, 1] * (c - a)[:, 0]) < 0
        f[flip] = f[flip][:, ::-1]
        i = len(self.V)
        self.V += [[x, y, z] for x, y in v]; self.UV += (v / uv_scale).tolist(); self.C += [col] * len(v)
        self.F += (f + i).tolist()


parts = {}


def part(surface, key):
    return parts.setdefault((surface,) + key, Part())


def rings(p):
    return [np.array(r.coords)[:, :2] for r in [p.exterior, *p.interiors]]


def walls(pt, p, z0, z1, uvfn, col, u0=0.0):
    """Wall quads around polygon p (CCW exterior faces out). uvfn(u, z) -> (U, V)."""
    for c in rings(p):
        u = u0
        for a, b in zip(c[:-1], c[1:]):
            L = float(np.hypot(*(b - a)))
            if L < 1e-3:
                continue
            pt.quad([[a[0], a[1], z0], [b[0], b[1], z0], [b[0], b[1], z1], [a[0], a[1], z1]],
                    [uvfn(u, z0), uvfn(u + L, z0), uvfn(u + L, z1), uvfn(u, z1)], col)
            u += L


def trim_uv(u, z):
    return [u / TRIM_TILE, -z / TRIM_TILE]


def polys(g):
    if g is None or g.is_empty: return []
    if isinstance(g, Polygon): return [g]
    if isinstance(g, MultiPolygon): return list(g.geoms)
    return [q for q in getattr(g, 'geoms', []) if isinstance(q, Polygon)]


def machine_rooms(p, rng):
    """Lift machine rooms along the long axis of a tall block, one per ~30 m (one per stairwell pair)."""
    rect = np.array(p.minimum_rotated_rectangle.exterior.coords)[:4]
    e1, e2 = rect[1] - rect[0], rect[2] - rect[1]
    axis = e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2
    L = float(np.linalg.norm(axis)); d = axis / L
    n = max(1, int(round(L / 30.0)))
    c = np.array(p.centroid.coords[0]); nrm = np.array([-d[1], d[0]])
    out = []
    for k in range(n):
        m = c + d * (L * ((k + 0.5) / n - 0.5)) + nrm * rng.uniform(-1.0, 1.0)
        w, h = rng.uniform(3.0, 4.5), rng.uniform(2.5, 3.5)
        corners = [m + d * sx * w / 2 + nrm * sy * h / 2 for sx, sy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
        box = shapely.geometry.polygon.orient(Polygon(corners), 1.0)
        if p.buffer(-1.0).contains(box):
            out.append(box)
    return out


feats = json.load(open(f'{MAP}/geojson/buildings.geojson'))['features']
counts = {}
for ft in feats:
    pr = ft['properties']
    ftype, h, base = pr['facade'], float(pr['height_m']), float(pr['base_z_m'])
    rng = np.random.default_rng(zlib.crc32(f"{pr['id']}{ft['geometry']['coordinates'][0][0]}".encode()))
    for p in polys(shape(ft['geometry'])):
        p = shapely.geometry.polygon.orient(p, 1.0)
        c = p.centroid
        key = (min(max(int((c.x + HALF) // TILE), 0), 3), min(max(int((c.y + HALF) // TILE), 0), 3))
        tint = TINTS[ftype][rng.integers(len(TINTS[ftype]))]
        shade = rng.uniform(0.93, 1.05)
        col = [int(np.clip(t * shade * 200, 0, 255)) for t in tint] + [255]   # 200 = 1.0, leaves room above
        tcol = [int(200 * rng.uniform(0.9, 1.05))] * 3 + [255]
        tw, th = FACADE_TILE[ftype]
        g0 = base + 0.5                      # lowest ground under the footprint
        top = base + h + 0.5
        pl = PLINTH.get(ftype, 0.0) if h > 4 else 0.0
        f0 = g0 + pl                         # facade texture starts here: floor 1 sits on the plinth
        u0 = float(rng.integers(0, 8)) * tw / 4.0 if ftype in ('panel', 'khrush', 'public') else rng.uniform(0, tw)

        def facade_uv(u, z, tw=tw, th=th, f0=f0):
            return [u / tw, -(z - f0) / th]

        # plinth (from below ground so slopes don't show a gap), facade, parapet band
        if pl > 0:
            walls(part('trim', key), p, base, f0, trim_uv, tcol)
        par = PARAPET.get(ftype, 0.0) if h >= 6 else 0.0
        walls(part(ftype, key), p, f0 if pl > 0 else base, top, facade_uv, col, u0)
        roof_poly = p
        if par > 0:
            inset = p.buffer(-PARAPET_W, join_style='mitre')
            if isinstance(inset, Polygon) and not inset.is_empty and inset.area > 0.5 * p.area:
                inset = shapely.geometry.polygon.orient(inset, -1.0)    # CW: inner face looks at the roof
                pt = part('trim', key)
                walls(pt, p, top, top + par, trim_uv, tcol)
                walls(pt, inset, top, top + par, trim_uv, tcol)
                pt.cap(p.difference(shapely.geometry.polygon.orient(inset, 1.0)), top + par, TRIM_TILE, tcol)
                roof_poly = shapely.geometry.polygon.orient(inset, 1.0)
        rcol = [int(200 * rng.uniform(0.85, 1.1))] * 3 + [255]
        part('roof', key).cap(roof_poly, top, ROOF_TILE, rcol)
        if ftype == 'panel' and h >= 20:
            for box in machine_rooms(roof_poly, rng):
                mh = rng.uniform(2.6, 3.4)
                pt = part('trim', key)
                walls(pt, box, top, top + mh, trim_uv, tcol)
                pt.cap(box, top + mh, TRIM_TILE, tcol)
        counts[ftype] = counts.get(ftype, 0) + 1

os.makedirs(f'{MAP}/meshes', exist_ok=True)
for f in os.listdir(f'{MAP}/meshes'):
    if f.startswith('bld_') and f.endswith('.glb'):
        os.remove(f'{MAP}/meshes/{f}')
faces = {}
for (surface, kx, ky), pt in sorted(parts.items()):
    if not pt.F:
        continue
    name = f'bld_{surface}_{kx}_{ky}'
    m = trimesh.Trimesh(np.array(pt.V, float), np.array(pt.F), process=False)
    m.visual = trimesh.visual.TextureVisuals(
        uv=np.array(pt.UV), material=trimesh.visual.material.PBRMaterial(name=f'bld_{surface}'))
    m.visual.vertex_attributes['color'] = np.array(pt.C, np.uint8)
    m.apply_transform(ZUP_TO_YUP)
    m.export(f'{MAP}/meshes/{name}.glb')
    faces[name] = len(m.faces)
print(json.dumps({'buildings': counts, 'meshes': len(faces), 'faces': sum(faces.values())}))
