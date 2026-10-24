# MapData

Real map data of the JBI district (Yekaterinburg), 4 x 4 km, built by `Tools/map/`.

| Path | What |
|---|---|
| `heightmap/jbi_heightmap_4033.png` | 16-bit landscape heightmap, 1 px = 1 m, row 0 = north |
| `heightmap/heightmap_info.json` | Landscape import scale/location |
| `masks/*.png` | Landscape paint layers (asphalt, paths, grass, forest, water, dirt) |
| `meshes/*.glb` | Building boxes, roads, paths, rails in 1 km tiles + `alignment_markers.glb` |
| `geojson/*.geojson` | All layers in local metres (0,0 = centre, X = east, Y = north) |
| `geojson/skate_spots.geojson` | Stairs, benches, ledges, plazas, dirt lots, schools |
| `preview_map.png` | Overview |

Licences: buildings/roads/POI © OpenStreetMap contributors (ODbL), Overture Maps Foundation, Microsoft Building Footprints (ODbL).
Terrain: Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA.
These credits must appear in the game credits.
