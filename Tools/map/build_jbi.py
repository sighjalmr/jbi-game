"""Build Unreal-ready data for the ЖБИ district (Yekaterinburg) from Overture Maps + Copernicus DEM.

Usage: python3 build_jbi.py <raw_dir> <dem.tif> <out_dir>

World frame: UTM 41N (EPSG:32641), origin at CENTER, 1 unit = 1 m.
  +X = east, +Y = north, Z = metres above the lowest terrain point in the area.
"""
import sys, os, json, math
import numpy as np
import pyarrow.parquet as pq
import shapely
from shapely.geometry import mapping, box, Polygon, MultiPolygon, LineString
from shapely.ops import transform as shp_transform
from pyproj import Transformer
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from rasterio.features import rasterize
from scipy.ndimage import gaussian_filter, map_coordinates
from PIL import Image
import trimesh

RAW, DEM, OUT = sys.argv[1:4]
CENTER_LONLAT = (60.683, 56.8315)
SIZE = 4033                     # px, UE-friendly landscape size (63x63 quads x 64 components)
RES = 1.0                       # m per px
HALF = (SIZE - 1) * RES / 2     # 2016 m
TILE = 1008.0                   # mesh tile size, m (4x4 tiles)

to_utm = Transformer.from_crs(4326, 32641, always_xy=True)
cx, cy = to_utm.transform(*CENTER_LONLAT)

def proj(g):
    def f(x, y, z=None):
        ex, ny = to_utm.transform(x, y)
        return np.asarray(ex) - cx, np.asarray(ny) - cy
    return shp_transform(f, g)

AREA = box(-HALF, -HALF, HALF, HALF)
for d in ['heightmap', 'geojson', 'meshes', 'masks']:
    os.makedirs(f'{OUT}/{d}', exist_ok=True)

# ---------------------------------------------------------------- terrain
src = rasterio.open(DEM)
dst = np.zeros((SIZE, SIZE), np.float32)
dst_tr = from_origin(cx - HALF - RES / 2, cy + HALF + RES / 2, RES, RES)  # row 0 = north edge
reproject(rasterio.band(src, 1), dst, dst_transform=dst_tr, dst_crs='EPSG:32641', resampling=Resampling.cubic)
# Copernicus is a surface model (roofs, trees): smooth so blocks of flats don't become hills.
dst = gaussian_filter(dst, sigma=25)
hmin, hmax = float(dst.min()), float(dst.max())
rng = hmax - hmin
h16 = np.round((dst - hmin) / rng * 65535).astype(np.uint16)
Image.fromarray(h16).save(f'{OUT}/heightmap/jbi_heightmap_{SIZE}.png')
h16.astype('<u2').tofile(f'{OUT}/heightmap/jbi_heightmap_{SIZE}.r16')
# Light version, 2 m per px: the full one can crash the editor on mid-range GPUs.
Image.fromarray(h16[::2, ::2]).save(f'{OUT}/heightmap/jbi_heightmap_{SIZE // 2 + 1}.png')
terrain = dst - hmin   # metres above lowest point

def ground(x, y):
    col = (np.atleast_1d(x) + HALF) / RES
    row = (HALF - np.atleast_1d(y)) / RES
    return map_coordinates(terrain, [row, col], order=1, mode='nearest')

zscale = rng * 100 / 512.0
info = {
    'source': 'Copernicus GLO-30 DSM, smoothed (sigma 25 m), resampled to 1 m',
    'size_px': SIZE, 'metres_per_px': RES, 'crs': 'EPSG:32641 (UTM 41N)',
    'center_lonlat': CENTER_LONLAT, 'center_utm': [cx, cy],
    'elevation_min_m': hmin, 'elevation_max_m': hmax, 'elevation_range_m': rng,
    'row0': 'north edge', 'col0': 'west edge',
    'unreal_landscape_import': {
        'scale_xyz': [100.0, 100.0, round(zscale, 4)],
        'location_xyz_cm': [0.0, 0.0, round(rng * 100 / 2, 2)],  # UE treats import Location as the landscape centre
        'section_size': '63x63 quads', 'sections_per_component': '1x1', 'components': '64x64',
    },
    'unreal_landscape_import_light': {
        'file': f'jbi_heightmap_{SIZE // 2 + 1}.png',
        'scale_xyz': [200.0, 200.0, round(zscale, 4)],
        'location_xyz_cm': [0.0, 0.0, round(rng * 100 / 2, 2)],
        'section_size': '63x63 quads', 'sections_per_component': '1x1', 'components': '32x32',
        'world_partition_region_size': 32,
    },
}
json.dump(info, open(f'{OUT}/heightmap/heightmap_info.json', 'w'), ensure_ascii=False, indent=2)

# ---------------------------------------------------------------- vector helpers
def load(name):
    p = f'{RAW}/{name}.parquet'
    return pq.read_table(p).to_pylist() if os.path.exists(p) else []

def name_of(r):
    return ((r.get('names') or {}).get('primary'))

def clip(g):
    g = proj(shapely.from_wkb(g))
    return g.intersection(AREA) if g.intersects(AREA) else None

def write_geojson(fname, feats):
    json.dump({'type': 'FeatureCollection', 'crs_note': 'local metres, origin=center, EPSG:32641 offset',
               'features': feats}, open(f'{OUT}/geojson/{fname}', 'w'), ensure_ascii=False)

def polys(g):
    if g is None or g.is_empty: return []
    if isinstance(g, Polygon): return [g]
    if isinstance(g, MultiPolygon): return list(g.geoms)
    return [p for p in getattr(g, 'geoms', []) if isinstance(p, Polygon)]

# ---------------------------------------------------------------- buildings
LOW = {'garage': 3, 'garages': 3, 'shed': 3, 'roof': 4, 'kiosk': 3, 'service': 4, 'house': 7, 'hut': 3,
       'cabin': 4, 'greenhouse': 3, 'carport': 3, 'transformer_tower': 6}
def est_height(r, area):
    if r.get('height'): return float(r['height']), 'osm_height'
    if r.get('num_floors'): return r['num_floors'] * 3.0 + 1.0, 'osm_floors'
    c = r.get('class')
    if c in LOW: return float(LOW[c]), 'class_default'
    if c in ('apartments', 'dormitory', 'residential'): return 28.0, 'class_default'
    if c in ('school', 'kindergarten'): return 10.0 if c == 'school' else 7.0, 'class_default'
    if area < 60: return 3.0, 'area_guess'
    if area < 250: return 6.0, 'area_guess'
    if area < 700: return 12.0, 'area_guess'
    return 28.0, 'area_guess'  # big footprints in ЖБИ are mostly 9-storey panel blocks

# Facade texture tile sizes in metres, must match Tools/art/gen_facades.py.
FACADE_TILE = {'panel': (12.8, 8.4), 'khrush': (12.0, 8.4), 'public': (12.0, 7.2), 'garage': (9.6, 3.0),
               'industrial': (12.0, 6.0)}
ROOF_TILE = 4.0
PUBLIC = {'school', 'kindergarten', 'college', 'university', 'hospital', 'clinic', 'civic', 'public', 'government',
          'retail', 'commercial', 'office', 'train_station', 'church', 'sports_hall', 'supermarket'}
SMALL = {'garage', 'garages', 'shed', 'carport', 'hut', 'service', 'transformer_tower', 'kiosk', 'roof', 'greenhouse'}
INDUSTRIAL = {'industrial', 'warehouse', 'manufacture', 'factory', 'hangar'}

def facade_type(r, area, h):
    c = r.get('class')
    if c in PUBLIC: return 'public'
    if c in SMALL or h <= 4: return 'garage'
    if c in INDUSTRIAL or (area > 1500 and h < 20 and c not in ('apartments', 'residential', 'dormitory')): return 'industrial'
    if h >= 20: return 'panel'
    return 'khrush'

def building_parts(p, base, top, ftype):
    """Walls with UVs in facade tiles (one tile = FACADE_TILE metres) and a flat roof with UVs in ROOF_TILE metres."""
    tw, th = FACADE_TILE[ftype]
    g0 = base + 0.5  # lowest ground under the footprint: floors start here
    p = shapely.geometry.polygon.orient(p, 1.0)
    V, F, UV = [], [], []
    for ring in [p.exterior, *p.interiors]:
        c = np.array(ring.coords)[:, :2]
        u = 0.0
        for a, b in zip(c[:-1], c[1:]):
            L = float(np.hypot(*(b - a)))
            if L < 1e-3: continue
            i = len(V)
            V += [[a[0], a[1], base], [b[0], b[1], base], [b[0], b[1], top], [a[0], a[1], top]]
            UV += [[u / tw, -(base - g0) / th], [(u + L) / tw, -(base - g0) / th],
                   [(u + L) / tw, -(top - g0) / th], [u / tw, -(top - g0) / th]]
            F += [[i, i + 1, i + 2], [i, i + 2, i + 3]]
            u += L
    walls = trimesh.Trimesh(np.array(V), np.array(F), process=False)
    walls.visual = trimesh.visual.TextureVisuals(uv=np.array(UV))
    v, f = trimesh.creation.triangulate_polygon(p, engine='earcut')
    a, b, c3 = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    flip = ((b - a)[:, 0] * (c3 - a)[:, 1] - (b - a)[:, 1] * (c3 - a)[:, 0]) < 0
    f[flip] = f[flip][:, ::-1]
    roof = trimesh.Trimesh(np.column_stack([v, np.full(len(v), top)]), f, process=False)
    roof.visual = trimesh.visual.TextureVisuals(uv=v / ROOF_TILE)
    return walls, roof

bfeats, bmeshes = [], {}
for r in load('buildings_building'):
    if r.get('is_underground'): continue
    g = clip(r['geometry'])
    for p in polys(g):
        if p.area < 8: continue
        p = shapely.make_valid(p.simplify(0.2))
        for p in polys(p):
            h, how = est_height(r, p.area)
            ftype = facade_type(r, p.area, h)
            xs, ys = np.array(p.exterior.coords).T
            base = float(ground(xs, ys).min()) - 0.5
            bfeats.append({'type': 'Feature', 'geometry': mapping(p), 'properties': {
                'id': r['id'], 'name': name_of(r), 'class': r.get('class'), 'height_m': h, 'height_source': how,
                'floors': r.get('num_floors'), 'base_z_m': round(base, 2), 'facade': ftype,
                'source': r['sources'][0]['dataset'] if r.get('sources') else None}})
            try:
                walls, roof = building_parts(p, base, base + h + 0.5, ftype)
            except Exception:
                continue
            c = p.centroid
            key = (min(max(int((c.x + HALF) // TILE), 0), 3), min(max(int((c.y + HALF) // TILE), 0), 3))
            bmeshes.setdefault((ftype,) + key, []).append(walls)
            bmeshes.setdefault(('roof',) + key, []).append(roof)
write_geojson('buildings.geojson', bfeats)

# ---------------------------------------------------------------- roads & rail
WIDTH = {'motorway': 16, 'trunk': 16, 'primary': 14, 'secondary': 11, 'tertiary': 8, 'residential': 6,
         'unclassified': 6, 'living_street': 5, 'service': 4, 'pedestrian': 4, 'track': 3, 'footway': 2,
         'path': 1.5, 'cycleway': 2, 'steps': 2, 'bridleway': 2, 'unknown': 4,
         'standard_gauge': 3.5, 'tram': 3, 'narrow_gauge': 2.5}
rfeats, rmeshes, road_polys = [], {}, {}
for r in load('transportation_segment'):
    cls = r.get('class') or 'unknown'
    if cls == 'subway': continue
    g = clip(r['geometry'])
    if g is None or g.is_empty: continue
    w = WIDTH.get(cls, 4)
    kind = 'rail' if r.get('subtype') == 'rail' else ('path' if cls in ('footway', 'path', 'cycleway', 'steps', 'bridleway', 'pedestrian') else 'road')
    rfeats.append({'type': 'Feature', 'geometry': mapping(g), 'properties': {
        'id': r['id'], 'name': name_of(r), 'class': cls, 'kind': kind, 'width_m': w,
        'surface': (r.get('road_surface') or [{}])[0].get('value') if r.get('road_surface') else None}})
    poly = shapely.segmentize(g, 4.0).buffer(w / 2, cap_style='flat', join_style='round', quad_segs=2)
    road_polys.setdefault(kind, []).append(poly)
write_geojson('roads.geojson', rfeats)

def drape(polyset, lift):
    out = {}
    u = shapely.union_all(polyset)
    for p in polys(u):
        p = shapely.segmentize(p, 6.0)
        try:
            v, f = trimesh.creation.triangulate_polygon(p, engine='earcut')
        except Exception:
            continue
        z = ground(v[:, 0], v[:, 1]) + lift
        m = trimesh.Trimesh(np.column_stack([v, z]), f, process=False)
        m.visual = trimesh.visual.TextureVisuals(uv=v / ROOF_TILE)  # 4 m texture tiles, world-aligned
        # split big road networks by tile of each face centroid
        cen = m.triangles_center
        keys = np.clip(np.floor((cen[:, :2] + HALF) / TILE).astype(int), 0, 3)
        for k in {tuple(k) for k in keys}:
            sel = np.all(keys == k, axis=1)
            sub = m.submesh([np.nonzero(sel)[0]], append=True)
            out.setdefault(k, []).append(sub)
    return out

road_layers = {kind: drape(ps, {'road': 0.25, 'path': 0.3, 'rail': 0.35}[kind]) for kind, ps in road_polys.items()}

# ---------------------------------------------------------------- water, landuse, greenery, POI
def area_layer(names, fname, propfn, keep=lambda r: True):
    feats, geoms = [], {}
    for n in names:
        for r in load(n):
            if not keep(r): continue
            g = clip(r['geometry'])
            if g is None or g.is_empty: continue
            props = propfn(r)
            feats.append({'type': 'Feature', 'geometry': mapping(g), 'properties': props})
            geoms.setdefault(props.get('layer'), []).append(g)
    write_geojson(fname, feats)
    return geoms

water = area_layer(['base_water'], 'water.geojson', lambda r: {'layer': 'water', 'class': r.get('class'), 'name': name_of(r)})
landuse = area_layer(['base_land_use'], 'landuse.geojson', lambda r: {'layer': r.get('subtype'), 'class': r.get('class'), 'name': name_of(r)})
land = area_layer(['base_land'], 'nature.geojson', lambda r: {'layer': r.get('subtype'), 'class': r.get('class'), 'name': name_of(r)})
area_layer(['base_infrastructure'], 'street_props.geojson', lambda r: {'layer': r.get('subtype'), 'class': r.get('class'), 'name': name_of(r)})
area_layer(['places_place'], 'poi.geojson', lambda r: {
    'layer': 'poi', 'name': name_of(r), 'category': (r.get('basic_category') or ''),
    'confidence': r.get('confidence')}, keep=lambda r: (r.get('confidence') or 0) >= 0.5)

# ---------------------------------------------------------------- landscape paint masks (8-bit, same grid as heightmap)
def mask(geoms, fname):
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms:
        a = np.zeros((SIZE, SIZE), np.uint8)
    else:
        tr = from_origin(-HALF - RES / 2, HALF + RES / 2, RES, RES)
        a = rasterize([(g, 255) for g in geoms], out_shape=(SIZE, SIZE), transform=tr, dtype=np.uint8, all_touched=True)
    Image.fromarray(a).save(f'{OUT}/masks/{fname}')
    return a

m_road = mask(road_polys.get('road', []) + road_polys.get('rail', []), 'mask_asphalt.png')
m_path = mask(road_polys.get('path', []), 'mask_paths.png')
m_water = mask([g.buffer(2) if g.geom_type.endswith('LineString') else g for g in water.get('water', [])], 'mask_water.png')
m_forest = mask(land.get('forest', []) + land.get('tree', []) + land.get('shrub', []), 'mask_forest.png')
m_grass = mask(landuse.get('managed', []) + landuse.get('park', []) + landuse.get('recreation', []) + land.get('grass', []), 'mask_grass.png')
m_dirt = mask(landuse.get('construction', []) + landuse.get('developed', []) + land.get('sand', []), 'mask_dirt_industrial.png')
# Packed for the landscape material (Tools/ue/landscape_material.py): R=paths G=forest B=dirt A=water.
packed = np.dstack([np.clip(gaussian_filter(c.astype(float), 1.5), 0, 255) for c in (m_path, m_forest, m_dirt, m_water)])
# Resize channel by channel: resizing an RGBA image premultiplies by alpha (water) and wipes the other masks.
Image.merge('RGBA', [Image.fromarray(packed[..., i].astype(np.uint8)).resize((4096, 4096), Image.BILINEAR)
                     for i in range(4)]).save(f'{OUT}/masks/landscape_masks.png')

# ---------------------------------------------------------------- meshes (glTF Y-up)
# (east, north, up) -> glTF (east, up, -north). Unreal 5.8's glTF importer maps glTF (x, y, z) to UE (x, z, y)
# (checked in the editor), so meshes land as UE X = east, Y = south, matching the landscape (row 0 = north = -Y).
ZUP_TO_YUP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float)
COLORS = {'buildings': [200, 196, 186, 255], 'road': [60, 60, 64, 255], 'path': [150, 140, 120, 255], 'rail': [110, 90, 70, 255]}

def export(meshes, name, color):
    if not meshes: return 0
    m = trimesh.util.concatenate(meshes)
    if color is None:  # textured: keep UVs, Unreal assigns the material by mesh name
        m.visual = trimesh.visual.TextureVisuals(uv=m.visual.uv, material=trimesh.visual.material.PBRMaterial(name=name.rsplit('_', 2)[0]))
    else:
        m.visual = trimesh.visual.ColorVisuals(m, face_colors=color)
    m.apply_transform(ZUP_TO_YUP)
    m.export(f'{OUT}/meshes/{name}.glb')
    return len(m.faces)

stats = {}
for (ftype, kx, ky), ms in bmeshes.items():
    stats[f'bld_{ftype}_{kx}_{ky}'] = export(ms, f'bld_{ftype}_{kx}_{ky}', None)
for kind, tiles in road_layers.items():
    for k, ms in tiles.items():
        stats[f'{kind}_{k[0]}_{k[1]}'] = export(ms, f'{kind}_{k[0]}_{k[1]}', None)

# alignment markers: 4 corner pillars + north arrow, sitting on the terrain
mk = []
for sx, sy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
    x, y = sx * (HALF - 20), sy * (HALF - 20)
    p = trimesh.creation.box([6, 6, 60]); p.apply_translation([x, y, float(ground(x, y)[0]) + 30]); mk.append(p)
arrow = trimesh.creation.extrude_polygon(Polygon([(-15, 0), (15, 0), (0, 60)]), 3)
arrow.apply_translation([0, 0, float(ground(0, 0)[0]) + 80]); mk.append(arrow)
export(mk, 'alignment_markers', [255, 40, 40, 255])

json.dump({'buildings': len(bfeats), 'segments': len(rfeats),
           'buildings_height_source': {s: sum(f['properties']['height_source'] == s for f in bfeats)
                                       for s in ['osm_height', 'osm_floors', 'class_default', 'area_guess']},
           'mesh_faces': stats, 'terrain': info}, open(f'{OUT}/build_report.json', 'w'), ensure_ascii=False, indent=2)

# ---------------------------------------------------------------- preview
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
fig, ax = plt.subplots(figsize=(14, 14), dpi=110)
ls = LightSource(azdeg=315, altdeg=40)
ax.imshow(ls.hillshade(terrain, vert_exag=3), cmap='gray', extent=[-HALF, HALF, -HALF, HALF], alpha=0.5)
def draw(gs, **kw):
    for g in gs:
        for p in polys(g):
            ax.fill(*p.exterior.xy, **kw)
draw(land.get('forest', []), color='#8fbf7f', lw=0)
draw(landuse.get('park', []) + landuse.get('managed', []), color='#c5e3b5', lw=0)
draw([g for g in water.get('water', []) if g.geom_type.endswith('Polygon')], color='#8cc4ef', lw=0)
for kind, col in [('path', '#b5a58a'), ('rail', '#7a5a40'), ('road', '#ffffff')]:
    draw(road_polys.get(kind, []), color=col, lw=0)
for f in bfeats:
    p = shapely.geometry.shape(f['geometry'])
    h = f['properties']['height_m']
    ax.fill(*p.exterior.xy, color=plt.cm.magma_r(min(h, 60) / 70), lw=0)
for t in np.arange(-HALF, HALF + 1, TILE):
    ax.axhline(t, color='k', lw=0.3, alpha=0.4); ax.axvline(t, color='k', lw=0.3, alpha=0.4)
ax.set_xlim(-HALF, HALF); ax.set_ylim(-HALF, HALF); ax.set_aspect('equal')
ax.set_title('ЖБИ, Екатеринбург — 4×4 км, цвет здания = высота (м). Сетка = тайлы 1 км', fontsize=13)
ax.text(-HALF + 20, -HALF + 20, '© OpenStreetMap contributors, Overture Maps Foundation, Microsoft; Copernicus DEM © ESA/Airbus',
        fontsize=8, bbox=dict(fc='white', alpha=0.7))
plt.savefig(f'{OUT}/preview_map.png', bbox_inches='tight')
print(json.dumps({'buildings': len(bfeats), 'segments': len(rfeats), 'hmin': hmin, 'hmax': hmax}, ensure_ascii=False))
