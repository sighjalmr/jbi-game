"""Plant the Megaplants trees from MapData/trees.csv (Tools/map/plant_trees.py) into JBI_World.

Run in the Unreal Editor with JBI_World open. Needs the free Fab items "Megaplants: Silver Birch" and
"Megaplants: Baltic Pine" in the project (they import as skinned Nanite trees with wind).
One actor per 256 m cell in the outliner folder "Trees", so World Partition streams them;
each holds an InstancedSkinnedMeshComponent per tree variant. Re-running replaces the old trees.
"""
import csv
import os
from collections import defaultdict

import unreal

CELL_CM = 25600.0
MESHES = {"birch": "/Game/Megaplant_Library/Tree_Silver_Birch/Tree_Silver_Birch_01/Tree_Silver_Birch_01_",
          "pine": "/Game/Megaplant_Library/Tree_Baltic_Pine/Tree_Baltic_Pine_01/Tree_Baltic_Pine_01_"}
END_CULL_CM = 60000

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
sdl = unreal.SubobjectDataBlueprintFunctionLibrary

actors.destroy_actors([a for a in actors.get_all_level_actors() if str(a.get_folder_path()).startswith("Trees")])

path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "MapData", "trees.csv")
cells = defaultdict(lambda: defaultdict(list))
with open(path, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        x, y = float(r["x_cm"]), float(r["y_cm"])
        cells[(int(x // CELL_CM), int(y // CELL_CM))][r["species"] + "_" + r["variant"]].append(
            unreal.Transform(unreal.Vector(x, y, float(r["z_cm"])), unreal.Rotator(0, 0, float(r["yaw"])),
                             unreal.Vector(1, 1, 1) * float(r["scale"])))

meshes = {}
for species, base in MESHES.items():
    for v in "ABCD":
        meshes[species + "_" + v] = unreal.load_asset(base + v)

placed = 0
for (cx, cy), groups in sorted(cells.items()):
    origin = unreal.Vector((cx + 0.5) * CELL_CM, (cy + 0.5) * CELL_CM, 0)
    actor = actors.spawn_actor_from_class(unreal.Actor, origin)
    actor.set_actor_label("Trees_{}_{}".format(cx, cy))
    actor.set_folder_path("Trees")
    root = sds.k2_gather_subobject_data_for_instance(actor)[0]
    scene, _ = sds.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=root, new_class=unreal.SceneComponent))
    for key, transforms in groups.items():
        handle, _ = sds.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=scene,
                                                                       new_class=unreal.InstancedSkinnedMeshComponent))
        comp = sdl.get_object(sdl.get_data(handle))
        sds.rename_subobject(handle, key)
        comp.set_skinned_asset_and_update(meshes[key])
        comp.set_editor_property("instance_end_cull_distance", END_CULL_CM)
        comp.set_editor_property("instance_start_cull_distance", END_CULL_CM - 10000)
        comp.add_instances(transforms, [0] * len(transforms), False, True)
        placed += len(transforms)

unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
unreal.log("JBI trees: {} trees in {} cells".format(placed, len(cells)))
