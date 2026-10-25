"""Swap the procedural ground textures for Quixel Megascans scans from Fab, and grow grass on the lawns.

Run in the Unreal Editor with JBI_World open, after apply_city_look.py and landscape_material.py.
Needs these free Fab items added to the project (Fab window > Add to project, medium quality):
  Asphalt Road, Concrete Pavement, Stone Gravel Mix, Wild Grass (surface), Forest Floor, Wild Grass (3D plant).
Roads, paths and rail beds get the scans through MI_asphalt / MI_paving / MI_ballast (reparented to M_JBI_Scan).
The landscape material is rebuilt from the same land-use masks with scan textures and a LandscapeGrassOutput,
so wild grass grows by itself on lawns (not on paths, dirt, forest floor or water).
"""
import unreal

FAB = "/Game/Fab/Megascans"
TEX_DEST = "/Game/JBI/Map/Textures"
MAT_DEST = "/Game/JBI/Map/Materials"
HALF_CM = 201600.0       # landscape half size
TILE_CM = 250.0          # one scan tile on the ground (scans cover 2x2 m)

# role -> Fab asset folder/id
SCANS = {
    "asphalt": "Surfaces/Asphalt_Road_tigkfb3o/Medium/tigkfb3o_tier_2/Textures/T_tigkfb3o_2K",
    "paving": "Surfaces/Concrete_Pavement_wjwjcis/Medium/wjwjcis_tier_2/Textures/T_wjwjcis_2K",
    "ballast": "Surfaces/Stone_Gravel_Mix_sexidbcb/Medium/sexidbcb_tier_2/Textures/T_sexidbcb_2K",
    "grass": "Surfaces/Wild_Grass_sfknaeoa/Medium/sfknaeoa_tier_2/Textures/T_sfknaeoa_2K",
    "forest": "Surfaces/Forest_Floor_sfjmafua/Medium/sfjmafua_tier_2/Textures/T_sfjmafua_2K",
}
GRASS_MESHES = FAB + "/Plants/Wild_Grass_vlkhcbxia/Medium/vlkhcbxia_tier_2/StaticMeshes/SM_vlkhcbxia_Var"

assets = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary


def scan(role):
    base = FAB + "/" + SCANS[role]
    bc, n, orm = (unreal.load_asset(base + s) for s in ("_B", "_N", "_ORM"))
    orm.set_editor_property("srgb", False)
    orm.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
    eal.save_loaded_asset(orm)
    return bc, n, orm


TEX = {role: scan(role) for role in SCANS}
SAMPLERS = [unreal.MaterialSamplerType.SAMPLERTYPE_COLOR, unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
            unreal.MaterialSamplerType.SAMPLERTYPE_MASKS]


def node(mat, cls, x, y, **props):
    n = mel.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n


def link(a, out, b, inp):
    mel.connect_material_expressions(a, out, b, inp)


def fresh(name):
    """An empty material at MAT_DEST/name; an existing one is cleared in place, since materials in use can't be deleted."""
    mat = unreal.load_asset(MAT_DEST + "/" + name)
    if mat:
        mel.delete_all_material_expressions(mat)
        return mat
    return assets.create_asset(name, MAT_DEST, unreal.Material, unreal.MaterialFactoryNew())


# ---------------------------------------------------------------- scan master for roads, paths, rail beds
scan_master = fresh("M_JBI_Scan")
uv = node(scan_master, unreal.MaterialExpressionTextureCoordinate, -1000, 0)
tiling = node(scan_master, unreal.MaterialExpressionScalarParameter, -1000, 150, parameter_name="Tiling", default_value=2.0)
uvt = node(scan_master, unreal.MaterialExpressionMultiply, -800, 0)
link(uv, "", uvt, "A"); link(tiling, "", uvt, "B")
s = []
for i, (param, st) in enumerate(zip(("BaseColor", "Normal", "ORM"), SAMPLERS)):
    t = node(scan_master, unreal.MaterialExpressionTextureSampleParameter2D, -600, -300 + i * 300,
             parameter_name=param, sampler_type=st, texture=TEX["asphalt"][i])
    link(uvt, "", t, "UVs")
    s.append(t)
mel.connect_material_property(s[0], "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
mel.connect_material_property(s[1], "RGB", unreal.MaterialProperty.MP_NORMAL)
mel.connect_material_property(s[2], "G", unreal.MaterialProperty.MP_ROUGHNESS)
mel.connect_material_property(s[2], "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
mel.recompile_material(scan_master)
eal.save_loaded_asset(scan_master)

for role in ("asphalt", "paving", "ballast"):
    mi = unreal.load_asset(MAT_DEST + "/MI_" + role)
    mel.set_material_instance_parent(mi, scan_master)
    for param, tex in zip(("BaseColor", "Normal", "ORM"), TEX[role]):
        mel.set_material_instance_texture_parameter_value(mi, param, tex)
    mel.set_material_instance_scalar_parameter_value(mi, "Tiling", 2.0)   # mesh UVs are 4 m per unit
    eal.save_loaded_asset(mi)

# ---------------------------------------------------------------- grass that grows on lawns
GT_PATH = MAT_DEST + "/LGT_JBI_WildGrass"
grass_type = unreal.load_asset(GT_PATH) if eal.does_asset_exist(GT_PATH) else assets.create_asset(
    "LGT_JBI_WildGrass", MAT_DEST, unreal.LandscapeGrassType, None)
varieties = []
for var in "ABCDEFGH":
    mesh = unreal.load_asset(GRASS_MESHES + var)
    if not mesh:
        continue
    v = unreal.GrassVariety()
    v.set_editor_property("grass_mesh", mesh)
    v.set_editor_property("grass_density", unreal.PerPlatformFloat(default=30.0))    # per 10 m2, per variety
    v.set_editor_property("start_cull_distance", unreal.PerPlatformInt(default=3000))
    v.set_editor_property("end_cull_distance", unreal.PerPlatformInt(default=6000))
    v.set_editor_property("scaling", unreal.GrassScaling.UNIFORM)
    v.set_editor_property("scale_x", unreal.FloatInterval(0.7, 1.2))
    v.set_editor_property("random_rotation", True)
    v.set_editor_property("align_to_surface", True)
    varieties.append(v)
grass_type.set_editor_property("grass_varieties", varieties)
for m in varieties[0].get_editor_property("grass_mesh").static_materials:     # cooked builds need the usage flag saved
    base = m.material_interface.get_base_material()
    base.set_editor_property("used_with_instanced_static_meshes", True)
    eal.save_loaded_asset(base)
eal.save_loaded_asset(grass_type)

# ---------------------------------------------------------------- landscape material from the masks
t = unreal.AssetImportTask()
t.filename = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()) + "MapData/masks/landscape_masks.png"
t.destination_path, t.automated, t.replace_existing, t.save = TEX_DEST, True, True, True
assets.import_asset_tasks([t])
masks = unreal.load_asset(TEX_DEST + "/landscape_masks")
masks.set_editor_property("srgb", False)
masks.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
masks.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
eal.save_loaded_asset(masks)
mat = fresh("M_JBI_Landscape")
wp = node(mat, unreal.MaterialExpressionWorldPosition, -2400, 0)
xy = node(mat, unreal.MaterialExpressionComponentMask, -2200, 0, r=True, g=True, b=False, a=False)
link(wp, "", xy, "")
uv_tile = node(mat, unreal.MaterialExpressionDivide, -2000, -200, const_b=TILE_CM)
link(xy, "", uv_tile, "A")
uv_macro = node(mat, unreal.MaterialExpressionDivide, -2000, -100, const_b=TILE_CM * 4.3)
link(xy, "", uv_macro, "A")
shift = node(mat, unreal.MaterialExpressionAdd, -2000, 200, const_b=HALF_CM)
link(xy, "", shift, "A")
uv_mask = node(mat, unreal.MaterialExpressionDivide, -1800, 200, const_b=HALF_CM * 2)
link(shift, "", uv_mask, "A")
mask = node(mat, unreal.MaterialExpressionTextureSample, -1600, 200, texture=masks,
            sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
link(uv_mask, "", mask, "UVs")

SHARED = unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS


def surface(role, y, uv):
    out = []
    for tex, st in zip(TEX[role], SAMPLERS):
        smp = node(mat, unreal.MaterialExpressionTextureSample, -1400, y, texture=tex, sampler_type=st, sampler_source=SHARED)
        link(uv, "", smp, "UVs")
        out.append(smp)
        y += 220
    return out


grass = surface("grass", -1600, uv_tile)
grass_macro = surface("grass", -900, uv_macro)
dirt = surface("ballast", -200, uv_tile)
forest = surface("forest", 500, uv_tile)
paving = surface("paving", 1200, uv_tile)
water = [node(mat, unreal.MaterialExpressionConstant3Vector, -1400, 1900, constant=unreal.LinearColor(0.03, 0.045, 0.05, 1)),
         node(mat, unreal.MaterialExpressionConstant3Vector, -1400, 2000, constant=unreal.LinearColor(0, 0, 1, 1)),
         node(mat, unreal.MaterialExpressionConstant, -1400, 2100, r=0.05)]


def lerp(a, a_out, b, b_out, alpha, alpha_out, x, y):
    l = node(mat, unreal.MaterialExpressionLinearInterpolate, x, y)
    link(a, a_out, l, "A"); link(b, b_out, l, "B"); link(alpha, alpha_out, l, "Alpha")
    return l


half = node(mat, unreal.MaterialExpressionConstant, -1000, -1700, r=0.45)
for i, (prop, out) in enumerate([(unreal.MaterialProperty.MP_BASE_COLOR, "RGB"),
                                 (unreal.MaterialProperty.MP_NORMAL, "RGB"),
                                 (unreal.MaterialProperty.MP_ROUGHNESS, "G")]):
    y = -600 + i * 600
    v = lerp(grass[i], out, grass_macro[i], out, half, "", -900, y)          # break up tiling
    v = lerp(v, "", dirt[i], out, mask, "B", -700, y)                        # industrial yards, construction (gravel)
    v = lerp(v, "", forest[i], out, mask, "G", -500, y)                      # birch and pine woods
    v = lerp(v, "", paving[i], out, mask, "R", -300, y)                      # footpaths and yards
    v = lerp(v, "", water[i], "", mask, "A", -100, y)                        # Shartash, ponds, Istok
    mel.connect_material_property(v, "", prop)

# lawn weight = no path, no dirt, no forest floor, no water
weight = None
for k, ch in enumerate("RGBA"):
    inv = node(mat, unreal.MaterialExpressionOneMinus, -700, 2300 + k * 80)
    link(mask, ch, inv, "")
    if weight is None:
        weight = inv
    else:
        m = node(mat, unreal.MaterialExpressionMultiply, -500, 2300 + k * 80)
        link(weight, "", m, "A"); link(inv, "", m, "B")
        weight = m
grass_out = node(mat, unreal.MaterialExpressionLandscapeGrassOutput, -200, 2300)
gi = unreal.GrassInput()
gi.set_editor_property("name", "Lawn")
gi.set_editor_property("grass_type", grass_type)
grass_out.set_editor_property("grass_types", [gi])
link(weight, "", grass_out, "Lawn")

mel.recompile_material(mat)
eal.save_loaded_asset(mat)

lands = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
         if isinstance(a, unreal.LandscapeProxy)]
for l in lands:
    l.set_editor_property("landscape_material", mat)
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
unreal.log("JBI megascans: {} scans, {} grass varieties, {} landscape actors".format(len(TEX), len(varieties), len(lands)))
