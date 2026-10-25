"""Tree positions for JBI_World: pines and birches in the real woods, birches in courtyards and parks.

Reads the outputs of build_jbi.py (MapData/masks, geojson, heightmap) and writes MapData/trees.csv:
species,variant,x_cm,y_cm,z_cm,yaw,scale in Unreal world space (X east, Y south, landscape heights).
Tools/ue/plant_trees.py places them in the level.
"""
import csv
import json
import os

import numpy as np
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.ndimage import binary_dilation
from shapely.geometry import shape

DATA = os.path.join(os.path.dirname(__file__), '..', '..', 'MapData')
SIZE, RES = 4033, 1.0
HALF = (SIZE - 1) * RES / 2          # 2016 m
FOREST_STEP = 10.0                   # metres between trees in the woods (jittered grid)
YARD_STEP = 14.0
YARD_KEEP = 0.35                     # courtyards are not woods: keep a third of the yard grid
YARD_LANDUSE = {'residential', 'park', 'school', 'kindergarten', 'university', 'grass', 'garden', 'playground'}
rng = np.random.default_rng(1971)


def mask(name):
    return np.array(Image.open(os.path.join(DATA, 'masks', name))) > 127


def features(name):
    with open(os.path.join(DATA, 'geojson', name), encoding='utf-8') as f:
        return json.load(f)['features']


def raster(geoms):
    tr = from_origin(-HALF - RES / 2, HALF + RES / 2, RES, RES)
    geoms = [g for g in geoms if not g.is_empty]
    return rasterize([(g, 1) for g in geoms], out_shape=(SIZE, SIZE), transform=tr, dtype=np.uint8, all_touched=True) > 0


roads = [shape(f['geometry']).buffer((f['properties'].get('width_m') or 4) / 2 + 2) for f in features('roads.geojson')]
blocked = raster([shape(f['geometry']).buffer(5) for f in features('buildings.geojson')] + roads)
blocked |= mask('mask_water.png') | binary_dilation(mask('mask_paths.png'), iterations=2)
yards = raster([shape(f['geometry']) for f in features('landuse.geojson') if f['properties'].get('class') in YARD_LANDUSE])
woods = mask('mask_forest.png') & ~blocked
yards &= ~blocked & ~woods & ~mask('mask_dirt_industrial.png')

# heights: 2017 px at 2 m, same import as the landscape (Z scale 25.4202, location Z 6507.57)
hm = np.array(Image.open(os.path.join(DATA, 'heightmap', 'jbi_heightmap_2017.png')), dtype=np.float64)


def ground_cm(x, y):
    c = np.clip(np.round((x + HALF) / 2).astype(int), 0, 2016)
    r = np.clip(np.round((HALF - y) / 2).astype(int), 0, 2016)
    return 6507.57 + (hm[r, c] - 32768) * 25.4202 / 128


def scatter(area, step):
    g = np.arange(-HALF + step / 2, HALF, step)
    x, y = np.meshgrid(g, g)
    x = x.ravel() + rng.uniform(-0.4, 0.4, x.size) * step
    y = y.ravel() + rng.uniform(-0.4, 0.4, y.size) * step
    col = np.clip(np.round(x + HALF).astype(int), 0, SIZE - 1)
    row = np.clip(np.round(HALF - y).astype(int), 0, SIZE - 1)
    keep = area[row, col]
    return x[keep], y[keep]


rows = []
for where, step, keep, pine_share in (('woods', FOREST_STEP, 1.0, 0.6), ('yards', YARD_STEP, YARD_KEEP, 0.15)):
    x, y = scatter(woods if where == 'woods' else yards, step)
    sel = rng.random(x.size) < keep
    x, y = x[sel], y[sel]
    z = ground_cm(x, y) - 10                     # sink the root flare a little
    pine = rng.random(x.size) < pine_share
    for i in range(x.size):
        rows.append(('pine' if pine[i] else 'birch', 'ABCD'[rng.integers(4)], round(x[i] * 100, 1), round(-y[i] * 100, 1),
                     round(z[i], 1), round(rng.uniform(0, 360), 1), round(rng.uniform(0.8, 1.15), 2)))

with open(os.path.join(DATA, 'trees.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['species', 'variant', 'x_cm', 'y_cm', 'z_cm', 'yaw', 'scale'])
    w.writerows(rows)
print('trees:', len(rows), {s: sum(r[0] == s for r in rows) for s in ('pine', 'birch')})
