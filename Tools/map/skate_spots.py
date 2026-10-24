"""Extract skate/BMX spots and gameplay hubs from the jbi-map geojson layers.
Usage: python3 skate_spots.py <jbi-map dir>"""
import sys, json, numpy as np, shapely
from shapely.geometry import shape, mapping
D = sys.argv[1]
load = lambda n: json.load(open(f'{D}/geojson/{n}.geojson'))['features']
spots = []
def add(g, kind, trick, name=None, **kw):
    spots.append({'type': 'Feature', 'geometry': mapping(g), 'properties': {'kind': kind, 'trick': trick, 'name': name, **kw}})
for f in load('roads'):
    p = f['properties']; g = shape(f['geometry'])
    if p['class'] == 'steps' and g.length >= 3:
        add(g.centroid, 'stairs', 'ollie/kickflip over stairs, handrail grind', p['name'], length_m=round(g.length, 1))
    if p['class'] == 'pedestrian':
        add(g.centroid, 'plaza', 'flatground, manuals', p['name'])
GRIND = {'bench': 'bench', 'wall': 'ledge', 'retaining_wall': 'ledge', 'kerb': 'curb', 'guard_rail': 'rail',
         'block': 'ledge', 'artwork': 'spot', 'fountain': 'spot', 'bus_stop': 'roof/bench'}
for f in load('street_props'):
    p = f['properties']; g = shape(f['geometry'])
    if p['class'] in GRIND:
        add(g.centroid if g.geom_type != 'Point' else g, GRIND[p['class']], 'grind/slide', p['name'])
    if p['class'] == 'parking' and g.area > 800:
        add(g.centroid, 'parking_lot', 'flatground, manual pads', p['name'], area_m2=round(g.area))
for f in load('landuse'):
    p = f['properties']; g = shape(f['geometry'])
    if p['class'] in ('plaza', 'pedestrian', 'pitch', 'recreation_ground', 'track'):
        add(g.centroid, p['class'], 'flatground / mini-ramp candidate', p['name'], area_m2=round(g.area))
    if p['class'] in ('quarry', 'construction', 'brownfield'):
        add(g.centroid, 'dirt', 'BMX dirt jumps', p['name'], area_m2=round(g.area))
    if p['class'] in ('school', 'college', 'university'):
        add(g.centroid, 'school', 'hub (Bully-style)', p['name'], area_m2=round(g.area))
# hotspot score: number of skateable features within 120 m
pts = np.array([[shape(s['geometry']).x, shape(s['geometry']).y] for s in spots])
sk = np.array([s['properties']['kind'] not in ('school',) for s in spots])
for i, s in enumerate(spots):
    d = np.hypot(*(pts[sk] - pts[i]).T)
    s['properties']['hotspot_score'] = int((d < 120).sum())
json.dump({'type': 'FeatureCollection', 'features': spots}, open(f'{D}/geojson/skate_spots.geojson', 'w'), ensure_ascii=False)
import collections
print(collections.Counter(s['properties']['kind'] for s in spots))
