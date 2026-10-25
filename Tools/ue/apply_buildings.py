"""Re-import only the building meshes (Tools/map/build_buildings.py output) with their own master material.

Run inside the Unreal Editor with JBI_World open, after apply_city_look.py has run once.
M_JBI_Building = M_JBI_Surface plus the per-building tint from the vertex colours. Building meshes are Nanite.
Replaces every actor in the outliner folders "Map/bld_*"; roads, paths and rails stay as they are.
"""
import os
import unreal

PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
MESH_SRC = os.path.join(PROJECT, "MapData", "meshes")
TEX_SRC = os.path.join(PROJECT, "MapData", "textures")
MESH_DEST = "/Game/JBI/Map/Meshes"
TEX_DEST = "/Game/JBI/Map/Textures"
MAT_DEST = "/Game/JBI/Map/Materials"
SURFACES = ["panel", "khrush", "public", "garage", "industrial", "roof", "trim"]
TINT_ONE = 255.0 / 200.0  # build_buildings.py stores an untinted building as vertex colour 200

assets = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
meshes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)


def import_files(files, dest):
    tasks = []
    for f in files:
        t = unreal.AssetImportTask()
        t.filename, t.destination_path = f, dest
        t.automated, t.replace_existing, t.save = True, True, True
        tasks.append(t)
    assets.import_asset_tasks(tasks)
    return tasks


# ---------------------------------------------------------------- textures (trim is new, roof was regenerated)
pngs = [os.path.join(TEX_SRC, s + suf + ".png") for s in ("trim", "roof") for suf in ("_BC", "_N", "_R")]
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

# ---------------------------------------------------------------- master material with vertex colour tint
MASTER = MAT_DEST + "/M_JBI_Building"
if eal.does_asset_exist(MASTER):
    master = unreal.load_asset(MASTER)
else:
    master = assets.create_asset("M_JBI_Building", MAT_DEST, unreal.Material, unreal.MaterialFactoryNew())
    bc = mel.create_material_expression(master, unreal.MaterialExpressionTextureSampleParameter2D, -900, -200)
    bc.set_editor_property("parameter_name", "BaseColor")
    bc.set_editor_property("texture", unreal.load_asset(TEX_DEST + "/panel_BC"))
    vc = mel.create_material_expression(master, unreal.MaterialExpressionVertexColor, -900, -450)
    one = mel.create_material_expression(master, unreal.MaterialExpressionConstant, -700, -450)
    one.set_editor_property("r", TINT_ONE)
    tint = mel.create_material_expression(master, unreal.MaterialExpressionMultiply, -500, -400)
    mel.connect_material_expressions(vc, "", tint, "A")
    mel.connect_material_expressions(one, "", tint, "B")
    col = mel.create_material_expression(master, unreal.MaterialExpressionMultiply, -300, -250)
    mel.connect_material_expressions(bc, "RGB", col, "A")
    mel.connect_material_expressions(tint, "", col, "B")
    nm = mel.create_material_expression(master, unreal.MaterialExpressionTextureSampleParameter2D, -900, 100)
    nm.set_editor_property("parameter_name", "Normal")
    nm.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    nm.set_editor_property("texture", unreal.load_asset(TEX_DEST + "/panel_N"))
    rg = mel.create_material_expression(master, unreal.MaterialExpressionTextureSampleParameter2D, -900, 400)
    rg.set_editor_property("parameter_name", "Roughness")
    rg.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_GRAYSCALE)
    rg.set_editor_property("texture", unreal.load_asset(TEX_DEST + "/panel_R"))
    mel.connect_material_property(col, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(nm, "RGB", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(rg, "R", unreal.MaterialProperty.MP_ROUGHNESS)
    master.set_editor_property("used_with_nanite", True)
    mel.recompile_material(master)
    eal.save_loaded_asset(master)

instances = {}
for surface in SURFACES:
    path = MAT_DEST + "/MI_" + surface
    mi = unreal.load_asset(path) if eal.does_asset_exist(path) else assets.create_asset(
        "MI_" + surface, MAT_DEST, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, master)
    for param, suffix in [("BaseColor", "_BC"), ("Normal", "_N"), ("Roughness", "_R")]:
        mel.set_material_instance_texture_parameter_value(mi, param, unreal.load_asset(TEX_DEST + "/" + surface + suffix))
    eal.save_loaded_asset(mi)
    instances[surface] = mi

# ---------------------------------------------------------------- replace the building actors
WPL = unreal.WorldPartitionBlueprintLibrary  # load unloaded World Partition cells first, or their old actors survive
WPL.load_actors([d.guid for d in WPL.get_actor_descs() if str(d.label).startswith("bld_")])
old = [a for a in actors.get_all_level_actors() if str(a.get_folder_path()).startswith("Map/bld_")]
actors.destroy_actors(old)

glbs = sorted(os.path.join(MESH_SRC, f) for f in os.listdir(MESH_SRC) if f.startswith("bld_") and f.endswith(".glb"))
tasks = import_files(glbs, MESH_DEST)
placed = 0
for task in tasks:
    name = os.path.splitext(os.path.basename(task.filename))[0]
    for path in task.imported_object_paths:
        mesh = unreal.load_asset(path)
        if not isinstance(mesh, unreal.StaticMesh):
            continue
        prefix = name.rsplit("_", 2)[0]
        for i in range(len(mesh.static_materials)):
            mesh.set_material(i, instances[prefix[len("bld_"):]])
        meshes.remove_collisions(mesh)
        mesh.get_editor_property("body_setup").set_editor_property(
            "collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        ns = mesh.get_editor_property("nanite_settings")
        ns.set_editor_property("enabled", True)
        meshes.set_nanite_settings(mesh, ns, apply_changes=True)
        eal.save_loaded_asset(mesh)
        actor = actors.spawn_actor_from_object(mesh, unreal.Vector(0, 0, 0))
        actor.set_actor_label(name)
        actor.set_folder_path("Map/" + prefix)
        placed += 1

unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
unreal.log("JBI buildings: {} materials, {} building meshes placed".format(len(instances), placed))
