"""Switch JBI_World to the retro look (PS2/PS3 era, Tony Hawk's American Wasteland style).

Run in the Unreal Editor with JBI_World open, after:
  python3 Tools/art/gen_retro.py MapData/textures      (small, saturated textures + tree atlas)
  python3 Tools/map/build_trees.py MapData             (low-poly trees)
Does, in order: re-imports the textures (facades, roofs, roads and ground get the retro versions in place),
puts roads back on M_JBI_Surface (off the Megascans), rebuilds the landscape material without 3D grass
(landscape_material.py), replaces the Megaplants trees with low-poly instanced ones, and sets simple lighting:
no Lumen, no virtual shadows, short cascaded sun shadows, flat sky light, coloured fog, punchy grading.
Megascans/Megaplants assets stay in the project, unused.
"""
import csv
import os
from collections import defaultdict

import unreal

PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
TEX_SRC = os.path.join(PROJECT, "MapData", "textures")
MESH_SRC = os.path.join(PROJECT, "MapData", "meshes")
TEX_DEST = "/Game/JBI/Map/Textures"
MAT_DEST = "/Game/JBI/Map/Materials"
TREE_DEST = "/Game/JBI/Trees"
CELL_CM = 102400.0
TREE_CULL_CM = 120000

assets = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
WPL = unreal.WorldPartitionBlueprintLibrary


def import_files(files, dest):
    tasks = []
    for f in files:
        t = unreal.AssetImportTask()
        t.filename, t.destination_path = f, dest
        t.automated, t.replace_existing, t.save = True, True, True
        tasks.append(t)
    assets.import_asset_tasks(tasks)
    return tasks


def setp(obj, **props):
    """Set what exists on this engine version; report the rest instead of failing the whole run."""
    for k, v in props.items():
        try:
            obj.set_editor_property(k, v)
        except Exception as e:
            unreal.log_warning("JBI retro: {}.{} not set ({})".format(obj.get_class().get_name(), k, e))


# ---------------------------------------------------------------- textures
pngs = sorted(os.path.join(TEX_SRC, f) for f in os.listdir(TEX_SRC)
              if f.endswith(".png") and not f.startswith("landscape_masks"))
import_files(pngs, TEX_DEST)
for f in pngs:
    name = os.path.splitext(os.path.basename(f))[0]
    tex = unreal.load_asset(TEX_DEST + "/" + name)
    if name.endswith("_N"):
        setp(tex, compression_settings=unreal.TextureCompressionSettings.TC_NORMALMAP, srgb=False)
    elif name.endswith("_R"):
        setp(tex, compression_settings=unreal.TextureCompressionSettings.TC_GRAYSCALE, srgb=False)
    eal.save_loaded_asset(tex)

# roads, paths and rail beds back on the plain surface material with the retro textures
surface = unreal.load_asset(MAT_DEST + "/M_JBI_Surface")
for role in ("asphalt", "paving", "ballast"):
    mi = unreal.load_asset(MAT_DEST + "/MI_" + role)
    mel.set_material_instance_parent(mi, surface)
    for param, suffix in [("BaseColor", "_BC"), ("Normal", "_N"), ("Roughness", "_R")]:
        mel.set_material_instance_texture_parameter_value(mi, param, unreal.load_asset(TEX_DEST + "/" + role + suffix))
    eal.save_loaded_asset(mi)

# landscape: own painted layers from the land-use masks, no LandscapeGrassOutput = no 3D grass
exec(open(os.path.join(PROJECT, "Tools", "ue", "landscape_material.py"), encoding="utf-8").read())

# ---------------------------------------------------------------- low-poly trees
TREE_MAT = TREE_DEST + "/M_JBI_Tree"
if eal.does_asset_exist(TREE_MAT):
    tree_mat = unreal.load_asset(TREE_MAT)
    mel.delete_all_material_expressions(tree_mat)
else:
    tree_mat = assets.create_asset("M_JBI_Tree", TREE_DEST, unreal.Material, unreal.MaterialFactoryNew())
atlas = unreal.load_asset(TEX_DEST + "/tree_atlas_BC")
smp = mel.create_material_expression(tree_mat, unreal.MaterialExpressionTextureSample, -500, 0)
smp.set_editor_property("texture", atlas)
mel.connect_material_property(smp, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
mel.connect_material_property(smp, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
rough = mel.create_material_expression(tree_mat, unreal.MaterialExpressionConstant, -300, 200)
rough.set_editor_property("r", 0.9)
mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
setp(tree_mat, blend_mode=unreal.BlendMode.BLEND_MASKED, two_sided=True, opacity_mask_clip_value=0.5,
     used_with_instanced_static_meshes=True)
mel.recompile_material(tree_mat)
eal.save_loaded_asset(tree_mat)

tree_meshes = {}
tasks = import_files([os.path.join(MESH_SRC, "tree_{}_{}.glb".format(s, v)) for s in ("pine", "birch") for v in "ABCD"],
                     TREE_DEST)
for task in tasks:
    key = os.path.splitext(os.path.basename(task.filename))[0][len("tree_"):]
    for path in task.imported_object_paths:
        mesh = unreal.load_asset(path)
        if isinstance(mesh, unreal.StaticMesh):
            for i in range(len(mesh.static_materials)):
                mesh.set_material(i, tree_mat)
            eal.save_loaded_asset(mesh)
            tree_meshes[key] = mesh

WPL.load_actors([d.guid for d in WPL.get_actor_descs() if str(d.label).startswith("Trees_")])
actors.destroy_actors([a for a in actors.get_all_level_actors() if str(a.get_folder_path()).startswith("Trees")])

sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
sdl = unreal.SubobjectDataBlueprintFunctionLibrary
cells = defaultdict(lambda: defaultdict(list))
with open(os.path.join(PROJECT, "MapData", "trees.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        x, y = float(r["x_cm"]), float(r["y_cm"])
        cells[(int(x // CELL_CM), int(y // CELL_CM))][r["species"] + "_" + r["variant"]].append(
            unreal.Transform(unreal.Vector(x, y, float(r["z_cm"]) - 20), unreal.Rotator(0, 0, float(r["yaw"])),
                             unreal.Vector(1, 1, 1) * float(r["scale"])))
placed = 0
for (cx, cy), groups in sorted(cells.items()):
    actor = actors.spawn_actor_from_class(unreal.Actor, unreal.Vector((cx + 0.5) * CELL_CM, (cy + 0.5) * CELL_CM, 0))
    actor.set_actor_label("Trees_{}_{}".format(cx, cy))
    actor.set_folder_path("Trees")
    root = sds.k2_gather_subobject_data_for_instance(actor)[0]
    scene, _ = sds.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=root, new_class=unreal.SceneComponent))
    for key, transforms in groups.items():
        handle, _ = sds.add_new_subobject(unreal.AddNewSubobjectParams(
            parent_handle=scene, new_class=unreal.HierarchicalInstancedStaticMeshComponent))
        sds.rename_subobject(handle, key)
        comp = sdl.get_object(sdl.get_data(handle))
        comp.set_static_mesh(tree_meshes[key])
        setp(comp, instance_end_cull_distance=TREE_CULL_CM, instance_start_cull_distance=TREE_CULL_CM - 20000)
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        comp.add_instances(transforms, False, True)
        placed += len(transforms)

# ---------------------------------------------------------------- light, sky, fog, grading
level = actors.get_all_level_actors()


def first(cls):
    return next((a for a in level if isinstance(a, cls)), None)


sun = first(unreal.DirectionalLight)
if sun:
    c = sun.get_component_by_class(unreal.DirectionalLightComponent)
    setp(c, light_color=unreal.Color(r=255, g=242, b=220, a=255), dynamic_shadow_distance_movable_light=15000.0,
         dynamic_shadow_cascades=3, cascade_distribution_exponent=3.0, cast_shadows=True)
sky = first(unreal.SkyLight)
if sky:
    c = sky.get_component_by_class(unreal.SkyLightComponent)
    setp(c, intensity=1.3, lower_hemisphere_color=unreal.LinearColor(0.12, 0.11, 0.09, 1.0))
    c.recapture_sky()
fog = first(unreal.ExponentialHeightFog)
if fog:
    c = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    setp(c, fog_density=0.03, start_distance=4000.0,
         fog_inscattering_luminance=unreal.LinearColor(0.42, 0.58, 0.85, 1.0))
clouds = first(unreal.VolumetricCloud)
if clouds:
    clouds.set_actor_hidden_in_game(True)
    clouds.set_is_temporarily_hidden_in_editor(True)

pp = next((a for a in level if isinstance(a, unreal.PostProcessVolume) and a.get_actor_label() == "RetroLook"), None)
if pp is None:
    pp = actors.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 10000))
    pp.set_actor_label("RetroLook")
    pp.set_folder_path("Lighting")
pp.set_editor_property("unbound", True)
s = pp.get_editor_property("settings")
for k, v in dict(
        dynamic_global_illumination_method=unreal.DynamicGlobalIlluminationMethod.NONE,
        reflection_method=unreal.ReflectionMethod.NONE,
        motion_blur_amount=0.0,
        bloom_intensity=0.35,
        ambient_occlusion_intensity=0.3,
        vignette_intensity=0.2,
        color_saturation=unreal.Vector4(1.0, 1.0, 1.0, 1.25),
        color_contrast=unreal.Vector4(1.0, 1.0, 1.0, 1.1),
        film_grain_intensity=0.0,
        scene_fringe_intensity=0.0).items():
    try:
        s.set_editor_property("override_" + k, True)
        s.set_editor_property(k, v)
    except Exception as e:
        unreal.log_warning("JBI retro: post process {} not set ({})".format(k, e))
pp.set_editor_property("settings", s)

for cmd in ("r.Shadow.Virtual.Enable 0", "r.AntiAliasingMethod 1", "r.DynamicGlobalIlluminationMethod 0",
            "r.ReflectionMethod 0", "r.DefaultFeature.MotionBlur 0"):
    unreal.SystemLibrary.execute_console_command(None, cmd)

unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
unreal.log("JBI retro: {} textures, {} trees in {} cells, lighting set".format(len(pngs), placed, len(cells)))
