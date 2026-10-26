extends Node3D
## Grass tufts in tiles around the camera; tiles appear and disappear as you ride.

@export var world_path: NodePath
@export var camera_path: NodePath
@export var tile := 16.0
@export var radius := 4            # tiles in each direction
@export var per_tile := 420

var world: WorldBuilder
var cam: Node3D
var density := PackedByteArray()
var _tiles := {}
var _mesh: ArrayMesh


func _ready() -> void:
	world = get_node(world_path)
	cam = get_node(camera_path)
	density = FileAccess.get_file_as_bytes("res://data/grass.bin")
	_mesh = _clump_mesh()


func _clump_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for k in 3:
		var a := PI * k / 3.0
		var d := Vector3(cos(a), 0, sin(a)) * 0.45
		var c := [-d, d, d + Vector3.UP * 0.5, -d + Vector3.UP * 0.5]
		var uv := [Vector2(0, 1), Vector2(1, 1), Vector2(1, 0), Vector2(0, 0)]
		for t in [[0, 1, 2], [0, 2, 3]]:
			for i in t:
				st.set_normal(Vector3.UP)     # lit like the ground under it
				st.set_uv(uv[i])
				st.add_vertex(c[i])
	var m := st.commit()
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = load("res://textures/foliage/grass_clump.png")
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	mat.alpha_scissor_threshold = 0.5
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.roughness = 0.9
	mat.vertex_color_use_as_albedo = true
	mat.distance_fade_mode = BaseMaterial3D.DISTANCE_FADE_PIXEL_DITHER
	mat.distance_fade_min_distance = tile * radius
	mat.distance_fade_max_distance = tile * (radius - 1.5)
	m.surface_set_material(0, mat)
	return m


func _density(x: float, z: float) -> float:
	var n := world.samples
	var ix := int(x + world.half)
	var iz := int(z + world.half)
	if ix < 0 or iz < 0 or ix >= n or iz >= n:
		return 0.0
	return density[iz * n + ix] / 255.0


func _process(_dt: float) -> void:
	var c := Vector2i(floori(cam.global_position.x / tile), floori(cam.global_position.z / tile))
	var keep := {}
	for dx in range(-radius, radius + 1):
		for dz in range(-radius, radius + 1):
			var key := c + Vector2i(dx, dz)
			keep[key] = true
			if not _tiles.has(key):
				_tiles[key] = _make_tile(key)
	for key in _tiles.keys():
		if not keep.has(key):
			if _tiles[key]:
				_tiles[key].queue_free()
			_tiles.erase(key)


func _make_tile(key: Vector2i) -> MultiMeshInstance3D:
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(key)
	var xf: Array[Transform3D] = []
	var cols: Array[Color] = []
	for i in per_tile:
		var x := (key.x + rng.randf()) * tile
		var z := (key.y + rng.randf()) * tile
		if rng.randf() > _density(x, z):
			continue
		var s := rng.randf_range(0.6, 1.3)
		var b := Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3(s, s * rng.randf_range(0.7, 1.2), s))
		xf.append(Transform3D(b, Vector3(x, world.height_at(x, z) - 0.03, z)))
		var g := rng.randf_range(0.75, 1.05)
		cols.append(Color(g, g, g * 0.9))
	if xf.is_empty():
		return null
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = _mesh
	mm.instance_count = xf.size()
	for i in xf.size():
		mm.set_instance_transform(i, xf[i])
		mm.set_instance_color(i, cols[i])
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mmi)
	return mmi
