"""Google Photorealistic 3D Tiles of ЖБИ as an editor-only reference layer in JBI_World.

Needs the Cesium for Unreal plugin (Fab, free) and a Google Maps Platform API key with the Map Tiles API enabled.
Put the key alone in Saved/google_maps_key.txt (Saved/ is not committed). Run in the editor with JBI_World open.

The layer is for checking building heights, entrances and yards by eye. It is editor-only and hidden in game:
Google's terms do not allow shipping or baking this data into the game.

Our world is UTM 41N with the origin at 56.8315N 60.683E. Cesium works in a local east-north-up frame, so the tileset
is rotated by the UTM grid convergence here (+1.94 deg) and scaled by the UTM scale factor (0.99984) to line up.
"""
import os
import unreal

ORIGIN_LAT, ORIGIN_LON = 56.8315, 60.683
GROUND_Z0_M = 179.10     # orthometric height of our Z = 0 (lowest point of the heightmap)
GEOID_N_M = 0.0          # geoid undulation here; tune if the Google mesh floats above or sinks below the landscape
CONVERGENCE_DEG = 1.94
UTM_SCALE = 0.99984

key_file = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "google_maps_key.txt")
if not os.path.exists(key_file):
    raise RuntimeError("Put your Google Maps API key into " + key_file)
key = open(key_file, encoding="utf-8").read().strip()

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level = actors.get_all_level_actors()

geo = next((a for a in level if isinstance(a, unreal.CesiumGeoreference)), None) or \
    actors.spawn_actor_from_class(unreal.CesiumGeoreference, unreal.Vector(0, 0, 0))
height = GROUND_Z0_M + GEOID_N_M
try:
    geo.set_origin_longitude_latitude_height(unreal.Vector(ORIGIN_LON, ORIGIN_LAT, height))
except AttributeError:
    geo.set_editor_property("origin_latitude", ORIGIN_LAT)
    geo.set_editor_property("origin_longitude", ORIGIN_LON)
    geo.set_editor_property("origin_height", height)
geo.set_folder_path("Reference")

for old in [a for a in level if isinstance(a, unreal.Cesium3DTileset) and a.get_actor_label() == "Google3D_Reference"]:
    actors.destroy_actor(old)
tiles = actors.spawn_actor_from_class(unreal.Cesium3DTileset, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, CONVERGENCE_DEG))
tiles.set_actor_label("Google3D_Reference")
tiles.set_folder_path("Reference")
tiles.set_actor_scale3d(unreal.Vector(UTM_SCALE, UTM_SCALE, 1.0))
tiles.set_editor_property("tileset_source", unreal.TilesetSource.FROM_URL)
tiles.set_editor_property("url", "https://tile.googleapis.com/v1/3dtiles/root.json?key=" + key)
tiles.set_editor_property("show_credits_on_screen", True)
tiles.set_actor_hidden_in_game(True)
tiles.set_editor_property("is_editor_only_actor", True)
tiles.set_actor_enable_collision(False)

# The tileset URL carries the API key, so keep its actor file out of git.
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
package = tiles.get_package().get_name()          # /Game/__ExternalActors__/...
rel = "Content/" + package[len("/Game/"):] + ".uasset"
gitignore = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), ".gitignore")
lines = open(gitignore, encoding="utf-8").read().splitlines() if os.path.exists(gitignore) else []
if rel not in lines:
    with open(gitignore, "a", encoding="utf-8") as f:
        f.write("\n# Google 3D reference tileset (its URL holds the API key)\n" + rel + "\n")

unreal.log("JBI: Google 3D reference added. Toggle it with the eye icon on Reference/Google3D_Reference.")
