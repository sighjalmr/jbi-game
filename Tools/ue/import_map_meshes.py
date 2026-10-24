"""Import the JBI map meshes (MapData/meshes/*.glb) and place them at the world origin.

Run inside the Unreal Editor: Tools > Execute Python Script... (needs the Python Editor Script Plugin,
already enabled in JBI.uproject). Open your map level first.
"""
import os
import unreal

SRC = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "MapData", "meshes")
DEST = "/Game/JBI/Map/Meshes"

tasks = []
for name in sorted(os.listdir(SRC)):
    if not name.endswith(".glb"):
        continue
    task = unreal.AssetImportTask()
    task.filename = os.path.join(SRC, name)
    task.destination_path = DEST
    task.automated = True
    task.replace_existing = True
    task.save = True
    tasks.append(task)

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
placed = 0
for task in tasks:
    for path in task.imported_object_paths:
        asset = unreal.load_asset(path)
        if isinstance(asset, unreal.StaticMesh):
            actor = actors.spawn_actor_from_object(asset, unreal.Vector(0, 0, 0))
            actor.set_folder_path("Map/" + os.path.splitext(os.path.basename(task.filename))[0].split("_")[0])
            placed += 1

unreal.log("JBI: imported {} files, placed {} meshes".format(len(tasks), placed))
