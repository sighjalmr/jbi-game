"""Cut a square piece of the JBI map and convert it for the Godot prototype.

Reads the district data (MapData/ in the repo, or the jbi-map folder) and writes
godot/data/: heights.bin, ground.png and chunk.json. Coordinates are converted to
Godot axes: X = east, Z = south, origin at the chunk centre, Y = up.

    python godot/tools/build_chunk.py --map MapData --center -180 1080 --size 640

Needs numpy, Pillow, shapely, mapbox_earcut.
"""
import argparse, json, math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import mapbox_earcut as earcut
from shapely.geometry import Polygon, LineString, box

ap = argparse.ArgumentParser()
ap.add_argument('--map', default=os.path.join(os.path.dirname(__file__), '..', '..', 'MapData'))
ap.add_argument('--center', type=float, nargs=2, default=[-180.0, 1080.0])
ap.add_argument('--size', type=int, default=640)
ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'data'))
a = ap.parse_args()

MAP, OUT = a.map, a.out
CX, CY = a.center
HALF = a.size // 2
N = a.size + 1                       # height samples, 1 m apart
GROUND_PX = 1024
FULL_HALF = 2016                     # the district heightmap is 4033 px, 1 m/px, centre at px 2016
rnd = random.Random(7)
os.makedirs(OUT, exist_ok=True)

def g(x, y):
    """District metres (x east, y north) -> Godot [X, Z] relative to the chunk centre."""
    return [round(x - CX, 2), round(CY - y, 2)]

clip = box(CX - HALF, CY - HALF, CX + HALF, CY + HALF)
inside = lambda x, y: abs(x - CX) <= HALF and abs(y - CY) <= HALF

# ---------------------------------------------------------------- heights
info = json.load(open(f'{MAP}/heightmap/heightmap_info.json'))
rng = info['elevation_range_m']
hm = np.array(Image.open(f'{MAP}/heightmap/jbi_heightmap_4033.png')).astype(np.float32) / 65535 * rng
c0, r0 = int(CX - HALF) + FULL_HALF, FULL_HALF - int(CY + HALF)
crop = hm[r0:r0 + N, c0:c0 + N]
z0 = float(crop.min())
(crop - z0).astype('<f4').tofile(f'{OUT}/heights.bin')   # row 0 = north (Z = -HALF)

# ---------------------------------------------------------------- vectors
def feats(name):
    return json.load(open(f'{MAP}/geojson/{name}.geojson'))['features']

def lines_of(geom):
    if geom['type'] == 'LineString': return [geom['coordinates']]
    if geom['type'] == 'MultiLineString': return geom['coordinates']
    return []

def clipped_lines(coords):
    ls = LineString([p[:2] for p in coords])
    if not ls.intersects(clip): return []
    part = ls.intersection(clip)
    parts = [part] if part.geom_type == 'LineString' else getattr(part, 'geoms', [])
    return [[g(x, y) for x, y in p.coords] for p in parts if p.geom_type == 'LineString' and p.length > 0.5]

def kind_of(p, h):
    c = p['class'] or ''
    if c in ('garages', 'garage', 'shed', 'roof'): return 'garage'
    if c in ('industrial', 'warehouse', 'service', 'transformer_tower'): return 'industrial'
    if c in ('school', 'kindergarten', 'retail', 'commercial', 'office', 'university', 'hospital', 'college', 'public', 'civic'): return 'public'
    if h >= 20: return 'panel'
    if h >= 10: return 'khrush'
    return 'garage' if h < 5 else 'public'

FAR_HALF = 1280                      # low-detail surroundings, so the chunk is not an island
far_clip = box(CX - FAR_HALF, CY - FAR_HALF, CX + FAR_HALF, CY + FAR_HALF)
buildings, far_buildings = [], []
for f in feats('buildings'):
    rings = f['geometry']['coordinates']
    poly = Polygon(rings[0], rings[1:])
    if not poly.is_valid: poly = poly.buffer(0)
    if poly.geom_type != 'Polygon': continue
    near = clip.contains(poly.centroid)
    if not near and not far_clip.contains(poly.centroid): continue
    p = f['properties']
    poly = poly.simplify(0.3 if near else 1.5)
    if poly.area < (6 if near else 40): continue
    outer = list(poly.exterior.coords)[:-1]
    holes = [list(r.coords)[:-1] for r in poly.interiors]
    verts = np.array(outer + [q for h in holes for q in h], dtype=np.float64)
    ends = np.cumsum([len(outer)] + [len(h) for h in holes]).astype(np.uint32)
    tri = earcut.triangulate_float64(verts, ends).tolist()
    h = float(p['height_m'])
    if kind_of(p, h) in ('panel', 'khrush'):
        h = max(2, round(h / 2.8)) * 2.8 + 0.6     # whole floors plus a parapet
    (buildings if near else far_buildings).append({
        'outer': [g(x, y) for x, y in outer], 'holes': [[g(x, y) for x, y in r] for r in holes],
        'tri': tri, 'base': round(p['base_z_m'] - z0, 2), 'h': round(h, 1),
        'k': kind_of(p, h), 'name': p.get('name')})

roads = []
for f in feats('roads'):
    p = f['properties']
    for c in lines_of(f['geometry']):
        for pts in clipped_lines(c):
            roads.append({'p': pts, 'w': p['width_m'], 'c': p['class'], 'k': p['kind'], 'name': p.get('name')})

ledges, props = [], {'lamp': [], 'bench': [], 'bin': [], 'bus_stop': [], 'tree': []}
for f in feats('street_props'):
    p, geo = f['properties'], f['geometry']
    c = p['class']
    if c in ('wall', 'retaining_wall', 'guard_rail', 'kerb'):
        for line in lines_of(geo):
            for pts in clipped_lines(line):
                ledges.append({'p': pts, 'c': c})
    elif geo['type'] == 'Point' and inside(*geo['coordinates'][:2]):
        key = {'street_lamp': 'lamp', 'lighting': 'lamp', 'bench': 'bench', 'waste_basket': 'bin',
               'waste_disposal': 'bin', 'bus_stop': 'bus_stop'}.get(c)
        if key: props[key].append(g(*geo['coordinates'][:2]))

# benches and bus stops face along the nearest path or road
def nearest_dir(pt):
    best, d_best = 0.0, 12.0
    for r in roads:
        q = r['p']
        for (ax, az), (bx, bz) in zip(q, q[1:]):
            dx, dz = bx - ax, bz - az
            L2 = dx * dx + dz * dz
            if L2 < 1e-6: continue
            t = max(0, min(1, ((pt[0] - ax) * dx + (pt[1] - az) * dz) / L2))
            d = math.hypot(ax + t * dx - pt[0], az + t * dz - pt[1])
            if d < d_best: best, d_best = math.atan2(dx, dz), d
    return round(best, 3)
for key in ('bench', 'bus_stop'):
    props[key] = [pt + [nearest_dir(pt)] for pt in props[key]]

spots = []
for f in feats('skate_spots'):
    x, y = f['geometry']['coordinates'][:2]
    if inside(x, y):
        spots.append({'p': g(x, y), 'kind': f['properties']['kind'], 'score': f['properties'].get('hotspot_score', 0)})

# ---------------------------------------------------------------- far ring: 16 m heights + 4 m/px ground colours
FAR_STEP = 16
fn = FAR_HALF * 2 // FAR_STEP + 1
xs = np.clip((CX - FAR_HALF + np.arange(fn) * FAR_STEP + FULL_HALF).astype(int), 0, 4032)
ys = np.clip((FULL_HALF - (CY - FAR_HALF + np.arange(fn) * FAR_STEP)).astype(int), 0, 4032)   # rows, north first
ys = ys[::-1]
(hm[np.ix_(ys, xs)] - z0).astype('<f4').tofile(f'{OUT}/far_heights.bin')

def far_colours(px=640):
    step = FAR_HALF * 2 / px
    gx = np.clip((CX - FAR_HALF + (np.arange(px) + 0.5) * step + FULL_HALF).astype(int), 0, 4032)
    gy = np.clip((FULL_HALF - (CY + FAR_HALF - (np.arange(px) + 0.5) * step)).astype(int), 0, 4032)
    img = np.ones((px, px, 3), np.float32) * np.array((100, 126, 60), np.float32)
    for k, col in (('grass', (96, 134, 52)), ('forest', (58, 82, 40)), ('dirt_industrial', (128, 112, 88)),
                   ('paths', (150, 140, 118)), ('asphalt', (92, 92, 96)), ('water', (52, 86, 104))):
        m = np.array(Image.open(f'{MAP}/masks/mask_{k}.png'))[np.ix_(gy, gx)] > 127
        img[m] = col
    r = np.random.default_rng(4).normal(0, 6, (px, px, 1))
    Image.fromarray(np.clip(img + r, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)).save(f'{OUT}/far_ground.png')
far_colours()

# ---------------------------------------------------------------- masks -> painted ground texture + trees
def mask(name):
    m = np.array(Image.open(f'{MAP}/masks/mask_{name}.png'))[r0:r0 + N, c0:c0 + N]
    return m > 127

M = {k: mask(k) for k in ('grass', 'forest', 'dirt_industrial', 'paths', 'asphalt', 'water')}

# footprints at 1 m/px: no trees inside buildings, and a dark rim on the ground around them
fp = Image.new('L', (N, N), 0)
dfp = ImageDraw.Draw(fp)
for b in buildings:
    dfp.polygon([(x + HALF, z + HALF) for x, z in b['outer']], fill=255)
built = np.array(fp) > 0

tree_pts = []
def scatter(m, cell, chance):
    for z in range(0, N - cell, cell):
        for x in range(0, N - cell, cell):
            if rnd.random() > chance: continue
            px, pz = x + rnd.uniform(0, cell), z + rnd.uniform(0, cell)
            ix, iz = int(px), int(pz)
            if m[iz, ix] and not (built[max(0, iz - 4):iz + 5, max(0, ix - 4):ix + 5].any()
                                  or M['asphalt'][iz, ix] or M['paths'][iz, ix] or M['water'][iz, ix]):
                tree_pts.append([round(px - HALF, 1), round(pz - HALF, 1)])
scatter(M['forest'], 6, 0.85)
scatter(M['grass'], 14, 0.35)
for f in feats('nature'):
    geo, c = f['geometry'], f['properties']['class']
    if c == 'tree' and geo['type'] == 'Point' and inside(*geo['coordinates'][:2]):
        tree_pts.append(g(*geo['coordinates'][:2]))
    if c == 'tree_row':
        for line in lines_of(geo):
            for pts in clipped_lines(line):
                ls = LineString(pts)
                for d in np.arange(0, ls.length, 7.0):
                    q = ls.interpolate(d); tree_pts.append([round(q.x, 1), round(q.y, 1)])
props['tree'] = tree_pts

def noise(scale, seed):
    r = np.random.default_rng(seed)
    s = max(2, GROUND_PX // scale)
    small = Image.fromarray((r.random((s, s)) * 255).astype(np.uint8))
    return np.array(small.resize((GROUND_PX, GROUND_PX), Image.BICUBIC)).astype(np.float32) / 255 - 0.5

def up(m):
    return np.array(Image.fromarray(m.astype(np.uint8) * 255).resize((GROUND_PX, GROUND_PX), Image.BILINEAR)
                    .filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32)[..., None] / 255

# splat for the terrain shader: R = paths, G = forest floor, B = dirt / industrial, A = asphalt; grass elsewhere
splat = np.concatenate([up(M['paths']), up(M['forest']), np.maximum(up(M['dirt_industrial']), up(M['water'])), up(M['asphalt'])], axis=2)
Image.fromarray((splat * 255).astype(np.uint8), 'RGBA').save(f'{OUT}/splat.png')
# where grass tufts grow (1 m/px, row 0 = north): grass and forest edges, not on paths, roads or under buildings
grass = (M['grass'] | M['forest']) & ~M['paths'] & ~M['asphalt'] & ~M['water'] & ~built
dens = np.where(M['grass'], 255, 110) * grass
Image.fromarray(dens.astype(np.uint8)).filter(ImageFilter.MinFilter(3)).save(f'{OUT}/grass_density.png')
np.array(Image.open(f'{OUT}/grass_density.png'), np.uint8).tofile(f'{OUT}/grass.bin')
os.remove(f'{OUT}/grass_density.png')
# macro tint: soft blotches so the tiling textures don't repeat visibly, darker around buildings
macro = 1.0 + noise(12, 1) * 0.35 + noise(48, 2) * 0.2
rim = np.array(fp.resize((GROUND_PX, GROUND_PX)).filter(ImageFilter.GaussianBlur(5))).astype(np.float32) / 255
macro *= 1 - 0.3 * rim
tint = np.stack([macro * 0.9, macro, macro * 0.86], axis=2) * 200
Image.fromarray(np.clip(tint, 0, 255).astype(np.uint8)).resize((512, 512), Image.BILINEAR).save(f'{OUT}/ground.png')

# spawn: top of the stairs on Vysotskogo, facing down the steps
spawn = g(-233.0, 1334.0)
json.dump({
    'size': a.size, 'samples': N, 'center_district_m': [CX, CY], 'z_offset_m': round(z0, 2),
    'spawn': {'p': spawn, 'yaw': round(math.atan2(-225.5 + 233.9, 1330.3 - 1292.9), 3)},
    'far': {'half': FAR_HALF, 'step': FAR_STEP, 'samples': int(fn), 'buildings': far_buildings},
    'buildings': buildings, 'roads': roads, 'ledges': ledges, 'props': props, 'spots': spots,
}, open(f'{OUT}/chunk.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print(f'far buildings {len(far_buildings)}, buildings {len(buildings)}, roads {len(roads)}, ledges {len(ledges)}, trees {len(tree_pts)}, '
      f'lamps {len(props["lamp"])}, benches {len(props["bench"])}, spots {len(spots)}, z0 {z0:.1f}')
