"""Give the JBI level real surfaces: facade/roof/road materials, textured building meshes.

Run inside the Unreal Editor with JBI_World open (Tools > Execute Python Script...).
Expects MapData/meshes/bld_*.glb (from Tools/map/build_jbi.py) and MapData/textures/*.png
(from Tools/art/gen_facades.py and gen_ground.py).
Replaces every actor in the outliner folder "Map" with the new meshes.
"""
import os
import unreal

PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
MESH_SRC = os.path.join(PROJECT, "MapData", "meshes")
TEX_SRC = os.path.join(PROJECT, "MapData", "textures")
MESH_DEST = "/Game/JBI/Map/Meshes"
TEX_DEST = "/Game/JBI/Map/Textures"
MAT_DEST = "/Game/JBI/Map/Materials"

assets = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
meshes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)

# mesh name prefix -> surface (texture set)
SURFACE = {"bld_panel": "panel", "bld_khrush": "khrush", "bld_public": "public", "bld_garage": "garage",
           "bld_industrial": "industrial", "bld_roof": "roof", "road": "asphalt", "path": "paving", "rail": "ballast"}


def import_files(files, dest):
    tasks = []
    for f in files:
        t = unreal.AssetImportTask()
        t.filename, t.destination_path = f, dest
        t.automated, t.replace_existing, t.save = True, True, True
        tasks.append(t)
    assets.import_asset_tasks(tasks)
    return tasks


# ---------------------------------------------------------------- textures
pngs = sorted(os.path.join(TEX_SRC, f) for f in os.listdir(TEX_SRC) if f.endswith(".png"))
import_files(pngs, TEX_DEST)
for f in pngs:
    name = os.path.splitext(os.path.basename(f))[0]
    tex = unreal.load_asset(TEX_DEST + "/" + name)
    if name.endswith("_N"):
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("srgb", False)
    elif name.endswith("_R"):
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
        tex.set_editor_property("srgb", False)
    eal.save_loaded_asset(tex)

# ---------------------------------------------------------------- master material
MASTER = MAT_DEST + "/M_JBI_Surface"
if eal.does_asset_exist(MASTER):
    master = unreal.load_asset(MASTER)
else:
    master = assets.create_asset("M_JBI_Surface", MAT_DEST, unreal.Material, unreal.MaterialFactoryNew())
    bc = mel.create_material_expression(master, unreal.MaterialExpressionTextureSampleParameter2D, -600, -200)
    bc.set_editor_property("parameter_name", "BaseColor")
    nm = mel.create_material_expression(master, unreal.MaterialExpressionTextureSampleParameter2D, -600, 100)
    nm.set_editor_property("parameter_name", "Normal")
    nm.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    nm.set_editor_property("texture", unreal.load_asset(TEX_DEST + "/panel_N"))
    rg = mel.create_material_expression(master, unreal.MaterialExpressionTextureSampleParameter2D, -600, 400)
    rg.set_editor_property("parameter_name", "Roughness")
    rg.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_GRAYSCALE)
    rg.set_editor_property("texture", unreal.load_asset(TEX_DEST + "/panel_R"))
    bc.set_editor_property("texture", unreal.load_asset(TEX_DEST + "/panel_BC"))
    mel.connect_material_property(bc, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(nm, "RGB", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(rg, "R", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(master)
    eal.save_loaded_asset(master)

# ---------------------------------------------------------------- one instance per surface
instances = {}
for surface in sorted(set(SURFACE.values())):
    path = MAT_DEST + "/MI_" + surface
    mi = unreal.load_asset(path) if eal.does_asset_exist(path) else assets.create_asset(
        "MI_" + surface, MAT_DEST, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, master)
    for param, suffix in [("BaseColor", "_BC"), ("Normal", "_N"), ("Roughness", "_R")]:
        mel.set_material_instance_texture_parameter_value(mi, param, unreal.load_asset(TEX_DEST + "/" + surface + suffix))
    eal.save_loaded_asset(mi)
    instances[surface] = mi

# ---------------------------------------------------------------- replace the map meshes
old = [a for a in actors.get_all_level_actors() if str(a.get_folder_path()).startswith("Map")]
actors.destroy_actors(old)

glbs = sorted(os.path.join(MESH_SRC, f) for f in os.listdir(MESH_SRC)
              if f.endswith(".glb") and f.split("_")[0] in ("bld", "road", "path", "rail", "alignment"))
tasks = import_files(glbs, MESH_DEST)
placed = 0
for task in tasks:
    name = os.path.splitext(os.path.basename(task.filename))[0]
    for path in task.imported_object_paths:
        mesh = unreal.load_asset(path)
        if not isinstance(mesh, unreal.StaticMesh):
            continue
        prefix = name.rsplit("_", 2)[0]
        if prefix in SURFACE:
            for i in range(len(mesh.static_materials)):
                mesh.set_material(i, instances[SURFACE[prefix]])
        meshes.remove_collisions(mesh)
        mesh.get_editor_property("body_setup").set_editor_property(
            "collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        eal.save_loaded_asset(mesh)
        actor = actors.spawn_actor_from_object(mesh, unreal.Vector(0, 0, 0))
        actor.set_actor_label(name)
        actor.set_folder_path("Map/" + prefix)
        if name.startswith("alignment"):
            actor.set_actor_enable_collision(False)
            actor.set_actor_hidden_in_game(True)
        placed += 1

unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
unreal.log("JBI look: {} textures, {} materials, {} map meshes placed".format(len(pngs), len(instances), placed))
