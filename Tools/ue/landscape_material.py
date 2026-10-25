"""Landscape material for JBI_World: grass, trampled dirt, forest floor, paving and water,
painted from the real land-use masks (MapData/masks/landscape_masks.png from build_jbi.py, R=paths G=forest B=dirt A=water).

Run in the Unreal Editor with JBI_World open, after apply_city_look.py (needs its textures).
"""
import os
import unreal

PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
TEX_DEST = "/Game/JBI/Map/Textures"
MAT_DEST = "/Game/JBI/Map/Materials"
HALF_CM = 201600.0       # landscape half size
TILE_CM = 400.0          # one ground texture tile = 4 m

assets = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary

t = unreal.AssetImportTask()
t.filename = os.path.join(PROJECT, "MapData", "masks", "landscape_masks.png")
if not os.path.exists(t.filename):
    t.filename = os.path.join(PROJECT, "MapData", "textures", "landscape_masks.png")
t.destination_path, t.automated, t.replace_existing, t.save = TEX_DEST, True, True, True
assets.import_asset_tasks([t])
masks = unreal.load_asset(TEX_DEST + "/landscape_masks")
masks.set_editor_property("srgb", False)
masks.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
masks.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
masks.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
eal.save_loaded_asset(masks)

PATH = MAT_DEST + "/M_JBI_Landscape"
if eal.does_asset_exist(PATH):      # in use by the landscape, so clear it in place instead of deleting
    mat = unreal.load_asset(PATH)
    mel.delete_all_material_expressions(mat)
else:
    mat = assets.create_asset("M_JBI_Landscape", MAT_DEST, unreal.Material, unreal.MaterialFactoryNew())

def node(cls, x, y, **props):
    n = mel.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n

def link(a, out, b, inp):
    mel.connect_material_expressions(a, out, b, inp)

wp = node(unreal.MaterialExpressionWorldPosition, -2400, 0)
xy = node(unreal.MaterialExpressionComponentMask, -2200, 0, r=True, g=True, b=False, a=False)
link(wp, "", xy, "")
uv_tile = node(unreal.MaterialExpressionDivide, -2000, -200, const_b=TILE_CM)
link(xy, "", uv_tile, "A")
uv_macro = node(unreal.MaterialExpressionDivide, -2000, -100, const_b=TILE_CM * 4.3)
link(xy, "", uv_macro, "A")
shift = node(unreal.MaterialExpressionAdd, -2000, 200, const_b=HALF_CM)
link(xy, "", shift, "A")
uv_mask = node(unreal.MaterialExpressionDivide, -1800, 200, const_b=HALF_CM * 2)
link(shift, "", uv_mask, "A")
mask = node(unreal.MaterialExpressionTextureSample, -1600, 200, texture=masks,
            sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
link(uv_mask, "", mask, "UVs")

SHARED = unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS

def surface(name, y, uv):
    out = []
    for suffix, st in [("_BC", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR),
                       ("_N", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL),
                       ("_R", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)]:
        s = node(unreal.MaterialExpressionTextureSample, -1400, y, texture=unreal.load_asset(TEX_DEST + "/" + name + suffix),
                 sampler_type=st, sampler_source=SHARED)
        link(uv, "", s, "UVs")
        out.append(s)
        y += 220
    return out

grass = surface("grass", -1600, uv_tile)
grass_macro = surface("grass", -900, uv_macro)
dirt = surface("dirt", -200, uv_tile)
forest = surface("forest", 500, uv_tile)
paving = surface("paving", 1200, uv_tile)
water_col = node(unreal.MaterialExpressionConstant3Vector, -1400, 1900, constant=unreal.LinearColor(0.04, 0.12, 0.18, 1))
water_n = node(unreal.MaterialExpressionConstant3Vector, -1400, 2000, constant=unreal.LinearColor(0, 0, 1, 1))
water_r = node(unreal.MaterialExpressionConstant, -1400, 2100, r=0.05)

def lerp(a, a_out, b, b_out, alpha, alpha_out, x, y):
    l = node(unreal.MaterialExpressionLinearInterpolate, x, y)
    link(a, a_out, l, "A"); link(b, b_out, l, "B"); link(alpha, alpha_out, l, "Alpha")
    return l

half = node(unreal.MaterialExpressionConstant, -1000, -1700, r=0.45)
for i, (prop, out) in enumerate([(unreal.MaterialProperty.MP_BASE_COLOR, "RGB"),
                                 (unreal.MaterialProperty.MP_NORMAL, "RGB"),
                                 (unreal.MaterialProperty.MP_ROUGHNESS, "R")]):
    y = -600 + i * 600
    v = lerp(grass[i], out, grass_macro[i], out, half, "", -900, y)          # break up tiling
    v = lerp(v, "", dirt[i], out, mask, "B", -700, y)                        # trampled yards, construction
    v = lerp(v, "", forest[i], out, mask, "G", -500, y)                      # birch and pine woods
    v = lerp(v, "", paving[i], out, mask, "R", -300, y)                      # footpaths and yards
    w = [water_col, water_n, water_r][i]
    v = lerp(v, "", w, "", mask, "A", -100, y)                               # Shartash, ponds, Istok
    mel.connect_material_property(v, "", prop)

mel.recompile_material(mat)
eal.save_loaded_asset(mat)

lands = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
         if isinstance(a, unreal.LandscapeProxy)]
for l in lands:
    l.set_editor_property("landscape_material", mat)
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
unreal.log("JBI landscape material on {} landscape actors".format(len(lands)))
