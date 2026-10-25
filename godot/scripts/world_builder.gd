extends Node3D
class_name WorldBuilder
## Builds the piece of ЖБИ at startup from godot/data (see tools/build_chunk.py):
## terrain, roads, buildings, trees, street props and the grind rails.

const DATA := "res://data/"
const TEX := "res://textures/"

## Lift above the terrain per road class, so crossing ribbons draw in a stable order.
const ROAD_LIFT := {
	"primary": 0.16, "secondary": 0.15, "tertiary": 0.14, "residential": 0.13,
	"living_street": 0.13, "unclassified": 0.13, "service": 0.12,
}
const MAIN_ROADS := ["primary", "secondary", "tertiary", "residential", "unclassified"]
const HANDRAIL_HEIGHT := 0.9
const BENCH_HEIGHT := 0.48
const CURB_HEIGHT := 0.16

var size := 640
var samples := 641
var half := 320.0
var heights := PackedFloat32Array()
var data: Dictionary
## Grind rails: each is {"pts": PackedVector3Array, "name": String}.
var rails: Array = []
var rail_grid := {}
var spawn_points: Array = []
var _mats := {}
var _road_grid := {}


func _ready() -> void:
	data = JSON.parse_string(FileAccess.get_file_as_string(DATA + "chunk.json"))
	size = int(data.size)
	samples = int(data.samples)
	half = size / 2.0
	heights = FileAccess.get_file_as_bytes(DATA + "heights.bin").to_float32_array()
	_index_roads()
	_build_terrain()
	_build_roads()
	_build_buildings(data.buildings, true, "")
	_build_buildings(data.far.buildings, false, "Far")
	_build_far_terrain()
	_build_bounds()
	_build_trees()
	_build_props()
	_build_rails()
	_collect_spawns()


# ---------------------------------------------------------------- helpers

func height_at(x: float, z: float) -> float:
	var fx := clampf(x + half, 0.0, samples - 1.001)
	var fz := clampf(z + half, 0.0, samples - 1.001)
	var ix := int(fx)
	var iz := int(fz)
	var tx := fx - ix
	var tz := fz - iz
	var i := iz * samples + ix
	var a := lerpf(heights[i], heights[i + 1], tx)
	var b := lerpf(heights[i + samples], heights[i + samples + 1], tx)
	return lerpf(a, b, tz)


func ground(p: Vector2, lift := 0.0) -> Vector3:
	return Vector3(p.x, height_at(p.x, p.y) + lift, p.y)


func mat(name: String, tex := "", opts := {}) -> StandardMaterial3D:
	if _mats.has(name):
		return _mats[name]
	var m := StandardMaterial3D.new()
	if tex != "":
		m.albedo_texture = load(TEX + tex + ".png")
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	m.vertex_color_use_as_albedo = true
	m.roughness = 0.9
	for k in opts:
		m.set(k, opts[k])
	_mats[name] = m
	return m


## PBR material from textures/pbr/<set>_albedo/_normal/_rough (see tools/import_pbr.py).
func pbr(name: String, set_name: String, opts := {}) -> StandardMaterial3D:
	if _mats.has(name):
		return _mats[name]
	var base := TEX + "pbr/" + set_name
	var o := {
		"albedo_texture": load(base + "_albedo.jpg"),
		"normal_enabled": true, "normal_texture": load(base + "_normal.png"),
		"roughness": 1.0, "roughness_texture": load(base + "_rough.jpg"),
		"roughness_texture_channel": BaseMaterial3D.TEXTURE_CHANNEL_GRAYSCALE,
	}
	o.merge(opts, true)
	return mat(name, "", o)


func _v2(a) -> Vector2:
	return Vector2(a[0], a[1])


func _line(arr) -> PackedVector2Array:
	var out := PackedVector2Array()
	for p in arr:
		out.append(_v2(p))
	return out


## Insert points so no segment is longer than `step` metres (ribbons then follow the terrain).
func _resample(pts: PackedVector2Array, step: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	for i in pts.size() - 1:
		var a := pts[i]
		var b := pts[i + 1]
		var n := maxi(1, ceili(a.distance_to(b) / step))
		for k in n:
			out.append(a.lerp(b, float(k) / n))
	out.append(pts[pts.size() - 1])
	return out


## Adds a triangle whose front face points along `n` (Godot draws clockwise faces as front).
func _tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, ua: Vector2, ub: Vector2, uc: Vector2, n: Vector3, col := Color.WHITE) -> void:
	if (b - a).cross(c - a).dot(n) > 0.0:
		var t := b; b = c; c = t
		var tu := ub; ub = uc; uc = tu
	st.set_normal(n); st.set_color(col); st.set_uv(ua); st.add_vertex(a)
	st.set_normal(n); st.set_color(col); st.set_uv(ub); st.add_vertex(b)
	st.set_normal(n); st.set_color(col); st.set_uv(uc); st.add_vertex(c)


func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, ua: Vector2, ub: Vector2, uc: Vector2, ud: Vector2, n: Vector3, col := Color.WHITE) -> void:
	_tri(st, a, b, c, ua, ub, uc, n, col)
	_tri(st, a, c, d, ua, uc, ud, n, col)


## A box stretched from a to b (used for rails, posts, benches).
func _beam(st: SurfaceTool, a: Vector3, b: Vector3, w: float, h: float, col: Color) -> void:
	var dir := b - a
	if dir.length() < 0.01:
		return
	var f := dir.normalized()
	var side := f.cross(Vector3.UP)
	if side.length() < 0.01:
		side = Vector3.RIGHT
	side = side.normalized() * w * 0.5
	var up := side.cross(f).normalized() * h * 0.5
	if up.y < 0:
		up = -up
	var c := [a - side - up, a + side - up, a + side + up, a - side + up]
	var e := [b - side - up, b + side - up, b + side + up, b - side + up]
	var uv := Vector2.ZERO
	for i in 4:
		var j := (i + 1) % 4
		var n: Vector3 = ((c[i] + c[j]) * 0.5 - a).normalized()
		_quad(st, c[i], c[j], e[j], e[i], uv, uv, uv, uv, n, col)
	_quad(st, c[0], c[1], c[2], c[3], uv, uv, uv, uv, -f, col)
	_quad(st, e[0], e[1], e[2], e[3], uv, uv, uv, uv, f, col)


func _add_mesh(st: SurfaceTool, m: Material, collide := false, name := "") -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = name
	if m is BaseMaterial3D and m.normal_enabled:
		st.generate_tangents()
	mi.mesh = st.commit()
	mi.material_override = m
	add_child(mi)
	if collide:
		var body := StaticBody3D.new()
		var shape := CollisionShape3D.new()
		shape.shape = mi.mesh.create_trimesh_shape()
		body.add_child(shape)
		mi.add_child(body)
	return mi


# ---------------------------------------------------------------- terrain

func _build_terrain() -> void:
	var step := 2
	var n := (samples - 1) / step + 1
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	var uvs := PackedVector2Array()
	var cols := PackedColorArray()
	var tangents := PackedFloat32Array()
	for j in n:
		for i in n:
			var x := -half + i * step
			var z := -half + j * step
			var h := height_at(x, z)
			verts.append(Vector3(x, h, z))
			var dx := height_at(x + 1, z) - height_at(x - 1, z)
			var dz := height_at(x, z + 1) - height_at(x, z - 1)
			normals.append(Vector3(-dx, 2.0, -dz).normalized())
			var t := Vector3(2.0, dx, 0.0).normalized()
			tangents.append_array([t.x, t.y, t.z, -1.0])
			uvs.append(Vector2(float(i) / (n - 1), float(j) / (n - 1)))
			cols.append(Color.WHITE)
	var idx := PackedInt32Array()
	for j in n - 1:
		for i in n - 1:
			var a := j * n + i
			# clockwise seen from above
			idx.append_array([a, a + 1, a + n, a + 1, a + n + 1, a + n])
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_NORMAL] = normals
	arr[Mesh.ARRAY_TEX_UV] = uvs
	arr[Mesh.ARRAY_COLOR] = cols
	arr[Mesh.ARRAY_TANGENT] = tangents
	arr[Mesh.ARRAY_INDEX] = idx
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	var mi := MeshInstance3D.new()
	mi.name = "Terrain"
	mi.mesh = mesh
	mi.material_override = terrain_material()
	add_child(mi)

	var body := StaticBody3D.new()
	body.name = "TerrainBody"
	var shape := CollisionShape3D.new()
	var hm := HeightMapShape3D.new()
	hm.map_width = samples
	hm.map_depth = samples
	hm.map_data = heights
	shape.shape = hm
	body.add_child(shape)
	add_child(body)


## Low-detail land around the playable square, with a hole where the chunk is.
func _build_far_terrain() -> void:
	var far: Dictionary = data.far
	var fh := FileAccess.get_file_as_bytes(DATA + "far_heights.bin").to_float32_array()
	var n := int(far.samples)
	var step := float(far.step)
	var fhalf := float(far.half)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var p := func(i: int, j: int) -> Vector3:
		return Vector3(-fhalf + i * step, fh[j * n + i] - 0.1, -fhalf + j * step)
	for j in n - 1:
		for i in n - 1:
			var a: Vector3 = p.call(i, j)
			var c: Vector3 = p.call(i + 1, j + 1)
			if a.x >= -half - 0.1 and c.x <= half + 0.1 and a.z >= -half - 0.1 and c.z <= half + 0.1:
				continue
			var b: Vector3 = p.call(i + 1, j)
			var d: Vector3 = p.call(i, j + 1)
			var uv := func(v: Vector3) -> Vector2: return Vector2(v.x + fhalf, v.z + fhalf) / (2.0 * fhalf)
			var nrm := (d - a).cross(b - a).normalized()
			_quad(st, a, b, c, d, uv.call(a), uv.call(b), uv.call(c), uv.call(d), nrm)
	_add_mesh(st, mat("far_ground", "", {"albedo_texture": load(DATA + "far_ground.png")}), false, "FarTerrain")
	# skirt along the chunk edge hides cracks between the two grids
	var sk := SurfaceTool.new()
	sk.begin(Mesh.PRIMITIVE_TRIANGLES)
	var g := terrain_material()
	for side in 4:
		for k in int(size / 2.0):
			var t0 := -half + k * 2.0
			var t1 := t0 + 2.0
			var a2: Vector2; var b2: Vector2; var out: Vector3
			match side:
				0: a2 = Vector2(t0, -half); b2 = Vector2(t1, -half); out = Vector3.FORWARD
				1: a2 = Vector2(t0, half); b2 = Vector2(t1, half); out = Vector3.BACK
				2: a2 = Vector2(-half, t0); b2 = Vector2(-half, t1); out = Vector3.LEFT
				_: a2 = Vector2(half, t0); b2 = Vector2(half, t1); out = Vector3.RIGHT
			var A := ground(a2); var B := ground(b2)
			var ua := (a2 + Vector2(half, half)) / size
			var ub := (b2 + Vector2(half, half)) / size
			_quad(sk, A, B, B - Vector3(0, 3, 0), A - Vector3(0, 3, 0), ua, ub, ub, ua, out)
	_add_mesh(sk, g, false, "Skirt")


## Invisible walls around the playable square.
func _build_bounds() -> void:
	for side in 4:
		var body := StaticBody3D.new()
		var shape := CollisionShape3D.new()
		var b := BoxShape3D.new()
		b.size = Vector3(size + 4.0, 400.0, 2.0) if side < 2 else Vector3(2.0, 400.0, size + 4.0)
		shape.shape = b
		body.add_child(shape)
		var off := half + 1.0
		body.position = [Vector3(0, 100, -off), Vector3(0, 100, off), Vector3(-off, 100, 0), Vector3(off, 100, 0)][side]
		add_child(body)


func terrain_material() -> ShaderMaterial:
	if _mats.has("terrain"):
		return _mats.terrain
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/terrain.gdshader")
	m.set_shader_parameter("splat", load(DATA + "splat.png"))
	m.set_shader_parameter("macro", load(DATA + "ground.png"))
	m.set_shader_parameter("chunk_size", float(size))
	for layer in [["grass", "grass"], ["path", "paving"], ["forest", "forest"], ["dirt", "dirt"], ["asphalt", "asphalt"]]:
		m.set_shader_parameter(layer[0] + "_albedo", load(TEX + "pbr/" + layer[1] + "_albedo.jpg"))
		m.set_shader_parameter(layer[0] + "_normal", load(TEX + "pbr/" + layer[1] + "_normal.png"))
	_mats.terrain = m
	return m


# ---------------------------------------------------------------- roads

func _index_roads() -> void:
	for r in data.roads:
		if r.k != "road" or not MAIN_ROADS.has(r.c):
			continue
		var pts := _line(r.p)
		for i in pts.size() - 1:
			var key := _cell(pts[i].lerp(pts[i + 1], 0.5), 16.0)
			if not _road_grid.has(key):
				_road_grid[key] = []
			_road_grid[key].append([pts[i], pts[i + 1], float(r.w) * 0.5])


func _cell(p: Vector2, s: float) -> Vector2i:
	return Vector2i(floori(p.x / s), floori(p.y / s))


## True when p lies on the carriageway of some main road (used to cut curbs at junctions).
func _on_road(p: Vector2, margin: float) -> bool:
	var c := _cell(p, 16.0)
	for dx in range(-2, 3):
		for dz in range(-2, 3):
			for seg in _road_grid.get(c + Vector2i(dx, dz), []):
				var q := Geometry2D.get_closest_point_to_segment(p, seg[0], seg[1])
				if q.distance_to(p) < seg[2] + margin:
					return true
	return false


func _ribbon(st: SurfaceTool, pts: PackedVector2Array, w: float, lift: float, uv_mode: int, col: Color, uv_scale := 4.0) -> void:
	pts = _resample(pts, 2.0)
	if pts.size() < 2:
		return
	var dist := 0.0
	var prev_l: Vector3
	var prev_r: Vector3
	var prev_d := 0.0
	for i in pts.size():
		var t: Vector2
		if i == 0:
			t = pts[1] - pts[0]
		elif i == pts.size() - 1:
			t = pts[i] - pts[i - 1]
		else:
			t = (pts[i + 1] - pts[i - 1])
		t = t.normalized()
		var nrm := Vector2(-t.y, t.x) * w * 0.5
		if i > 0:
			dist += pts[i].distance_to(pts[i - 1])
		var l := ground(pts[i] + nrm, lift)
		var r := ground(pts[i] - nrm, lift)
		if i > 0:
			var ua: Vector2; var ub: Vector2; var uc: Vector2; var ud: Vector2
			if uv_mode == 0:   # world-planar, seamless where ribbons overlap
				ua = Vector2(prev_l.x, prev_l.z) / uv_scale; ub = Vector2(prev_r.x, prev_r.z) / uv_scale
				uc = Vector2(r.x, r.z) / uv_scale; ud = Vector2(l.x, l.z) / uv_scale
			else:              # along the line (stairs)
				ua = Vector2(0, prev_d / uv_scale); ub = Vector2(1, prev_d / uv_scale)
				uc = Vector2(1, dist / uv_scale); ud = Vector2(0, dist / uv_scale)
			_quad(st, prev_l, prev_r, r, l, ua, ub, uc, ud, Vector3.UP, col)
		prev_l = l; prev_r = r; prev_d = dist


func _build_roads() -> void:
	var asphalt := SurfaceTool.new(); asphalt.begin(Mesh.PRIMITIVE_TRIANGLES)
	var pave := SurfaceTool.new(); pave.begin(Mesh.PRIMITIVE_TRIANGLES)
	var stairs := SurfaceTool.new(); stairs.begin(Mesh.PRIMITIVE_TRIANGLES)
	var paint := SurfaceTool.new(); paint.begin(Mesh.PRIMITIVE_TRIANGLES)
	var curb := SurfaceTool.new(); curb.begin(Mesh.PRIMITIVE_TRIANGLES)
	var trail := SurfaceTool.new(); trail.begin(Mesh.PRIMITIVE_TRIANGLES)
	var ballast := SurfaceTool.new(); ballast.begin(Mesh.PRIMITIVE_TRIANGLES)
	var k := 0
	for r in data.roads:
		var pts := _line(r.p)
		if pts.size() < 2:
			continue
		k += 1
		var jitter := (k % 7) * 0.002
		if r.c == "steps":
			_ribbon(stairs, pts, maxf(2.5, r.w), 0.1, 1, Color.WHITE, 2.8)
			_add_handrails(pts, maxf(2.5, r.w))
		elif r.k == "road":
			var w := float(r.w)
			_ribbon(asphalt, pts, w, ROAD_LIFT.get(r.c, 0.12) + jitter, 0, Color.WHITE, 4.0)
			if r.c in ["primary", "secondary", "tertiary"]:
				_dashes(paint, pts, ROAD_LIFT.get(r.c, 0.12) + 0.02)
			if MAIN_ROADS.has(r.c):
				_curbs(curb, pts, w)
		elif r.k == "rail":
			_ribbon(ballast, pts, float(r.w), 0.05 + jitter, 0, Color.WHITE, 4.0)
		else:
			var w := maxf(1.6, float(r.w))
			if r.c in ["path", "track"]:   # dirt trail through the park
				_ribbon(trail, pts, w, 0.05 + jitter, 0, Color.WHITE, 4.0)
			else:
				_ribbon(pave, pts, w, 0.07 + jitter, 0, Color.WHITE, 4.0)
	_add_mesh(asphalt, pbr("asphalt", "asphalt"), false, "Roads")
	_add_mesh(pave, pbr("paving", "paving"), false, "Paths")
	_add_mesh(trail, pbr("trail", "dirt"), false, "Trails")
	_add_mesh(ballast, pbr("ballast", "ballast"), false, "Railway")
	_add_mesh(stairs, mat("stairs", "stairs", {"albedo_color": Color(0.85, 0.84, 0.82)}), false, "Stairs")
	_add_mesh(paint, mat("paint", "", {"albedo_color": Color(0.85, 0.84, 0.78), "roughness": 0.7}), false, "Markings")
	_add_mesh(curb, mat("curb", "concrete", {"albedo_color": Color(0.8, 0.8, 0.78)}), false, "Curbs")


func _dashes(st: SurfaceTool, pts: PackedVector2Array, lift: float) -> void:
	pts = _resample(pts, 1.5)
	var d := 0.0
	var seg := PackedVector2Array()
	for i in pts.size():
		if i > 0:
			d += pts[i].distance_to(pts[i - 1])
		var on := fmod(d, 6.0) < 3.0
		if on:
			seg.append(pts[i])
		elif seg.size() > 1:
			_ribbon(st, seg, 0.15, lift, 0, Color.WHITE)
			seg = PackedVector2Array()
		else:
			seg = PackedVector2Array()
	if seg.size() > 1:
		_ribbon(st, seg, 0.15, lift, 0, Color.WHITE)


## Concrete curbs on both sides of a main road; they double as low grind ledges.
func _curbs(st: SurfaceTool, pts: PackedVector2Array, w: float) -> void:
	pts = _resample(pts, 2.0)
	for side: float in [-1.0, 1.0]:
		var run := PackedVector3Array()
		for i in pts.size():
			var t := (pts[mini(i + 1, pts.size() - 1)] - pts[maxi(i - 1, 0)]).normalized()
			var p := pts[i] + Vector2(-t.y, t.x) * side * (w * 0.5 + 0.15)
			if _on_road(p, 0.3):
				_flush_curb(st, run)
				run = PackedVector3Array()
				continue
			run.append(ground(p, CURB_HEIGHT))
		_flush_curb(st, run)


func _flush_curb(st: SurfaceTool, run: PackedVector3Array) -> void:
	if run.size() < 3:
		return
	for i in run.size() - 1:
		_beam(st, run[i] - Vector3(0, CURB_HEIGHT * 0.5 + 0.05, 0), run[i + 1] - Vector3(0, CURB_HEIGHT * 0.5 + 0.05, 0), 0.3, CURB_HEIGHT + 0.1, Color(0.95, 0.95, 0.92))
	_add_rail(run, "Curb Grind")


# ---------------------------------------------------------------- buildings

## facade texture set, tile width and height in metres (the tile is 4 bays wide)
const FACADE := {
	"panel": ["panel", 12.8, 8.4], "panel_b": ["panel", 12.8, 8.4],
	"khrush": ["khrush", 12.0, 8.4], "public": ["public", 12.0, 7.2],
	"garage": ["garage", 9.6, 3.0], "industrial": ["industrial", 12.0, 6.0],
}
const PARAPET := 0.6


func _build_buildings(list: Array, collide: bool, prefix: String) -> void:
	var walls := {}
	for kname in FACADE:
		walls[kname] = SurfaceTool.new()
		walls[kname].begin(Mesh.PRIMITIVE_TRIANGLES)
	var roof := SurfaceTool.new(); roof.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rng := RandomNumberGenerator.new()
	rng.seed = 42
	for b in list:
		var kname: String = b.k
		if kname == "panel" and rng.randf() < 0.4:
			kname = "panel_b"
		var tint := Color.from_hsv(rng.randf_range(0.05, 0.14), rng.randf_range(0.0, 0.08), rng.randf_range(1.0, 1.12))
		if kname == "panel_b":
			tint = tint * Color(1.0, 0.95, 0.85)
		var base := float(b.base)
		var outer := _line(b.outer)
		var lo := INF
		for p in outer:
			lo = minf(lo, height_at(p.x, p.y) if collide else base)
		var bottom := minf(base, lo) - 1.5
		var top := maxf(base, lo) + float(b.h)
		var rings := [outer]
		for hole in b.holes:
			rings.append(_line(hole))
		for ri in rings.size():
			var ring: PackedVector2Array = rings[ri]
			# outward normals: the outer ring and holes wind opposite ways
			var cw := _signed_area(ring) > 0.0
			if ri > 0:
				cw = not cw
			_walls(walls[kname], ring, bottom, top, base, FACADE[kname], cw, tint)
			if collide:
				_parapet(roof, ring, top, cw)
		var all := PackedVector2Array()
		for ring in rings:
			all.append_array(ring)
		var tri: Array = b.tri
		var roof_y := top - (PARAPET * 0.8 if collide else 0.0)
		for t in range(0, tri.size(), 3):
			var pa := all[int(tri[t])]; var pb := all[int(tri[t + 1])]; var pc := all[int(tri[t + 2])]
			_tri(roof, Vector3(pa.x, roof_y, pa.y), Vector3(pb.x, roof_y, pb.y), Vector3(pc.x, roof_y, pc.y),
				pa / 4.0, pb / 4.0, pc / 4.0, Vector3.UP, tint)
	for kname in walls:
		_add_mesh(walls[kname], pbr("wall_" + FACADE[kname][0], FACADE[kname][0]), collide, prefix + "Walls_" + kname)
	_add_mesh(roof, pbr("roof", "roof"), collide, prefix + "Roofs")


## Inner face and cap of the low wall around a flat roof.
func _parapet(st: SurfaceTool, ring: PackedVector2Array, top: float, cw: bool) -> void:
	var low := top - PARAPET * 0.8
	var cap := Color(0.75, 0.74, 0.72)
	for i in ring.size():
		var a := ring[i]
		var b := ring[(i + 1) % ring.size()]
		var len := a.distance_to(b)
		if len < 0.05:
			continue
		var d := (b - a) / len
		var out2 := Vector2(d.y, -d.x) if cw else Vector2(-d.y, d.x)
		var inn := -out2 * 0.25
		var A := Vector3(a.x + inn.x, low, a.y + inn.y); var B := Vector3(b.x + inn.x, low, b.y + inn.y)
		var At := Vector3(A.x, top, A.z); var Bt := Vector3(B.x, top, B.z)
		var n := Vector3(-out2.x, 0, -out2.y)
		_quad(st, A, B, Bt, At, Vector2(0, 0.2), Vector2(len / 4.0, 0.2), Vector2(len / 4.0, 0), Vector2(0, 0), n, cap)
		var Ot := Vector3(a.x, top, a.y); var Pt := Vector3(b.x, top, b.y)
		_quad(st, Ot, Pt, Bt, At, Vector2(0, 0), Vector2(len / 4.0, 0), Vector2(len / 4.0, 0.06), Vector2(0, 0.06), Vector3.UP, cap)


func _signed_area(ring: PackedVector2Array) -> float:
	var s := 0.0
	for i in ring.size():
		var a := ring[i]
		var b := ring[(i + 1) % ring.size()]
		s += a.x * b.y - b.x * a.y
	return s * 0.5


func _walls(st: SurfaceTool, ring: PackedVector2Array, bottom: float, top: float, base: float, f: Array, cw: bool, tint: Color) -> void:
	var u := 0.0
	var tw: float = f[1]
	var th: float = f[2]
	for i in ring.size():
		var a := ring[i]
		var b := ring[(i + 1) % ring.size()]
		var len := a.distance_to(b)
		if len < 0.05:
			continue
		var d := (b - a) / len
		var n2 := Vector2(d.y, -d.x) if cw else Vector2(-d.y, d.x)
		var n := Vector3(n2.x, 0, n2.y)
		# snap facade repeats to whole windows so corners don't cut a window in half
		var u0 := u
		var u1 := u + maxf(1.0, roundf(len / (tw / 4.0))) * 0.25
		u = u1
		# v counts floors up from the base, so window rows sit on real floor heights
		var v := func(y: float) -> float: return 1.0 - (y - base) / th
		var dark := tint * Color(0.8, 0.8, 0.82)
		var mid := clampf(base + 1.2, bottom + 0.1, top - 0.1)
		var A := Vector3(a.x, bottom, a.y); var B := Vector3(b.x, bottom, b.y)
		var Am := Vector3(a.x, mid, a.y); var Bm := Vector3(b.x, mid, b.y)
		var At := Vector3(a.x, top, a.y); var Bt := Vector3(b.x, top, b.y)
		var vb: float = v.call(bottom)
		var vm: float = v.call(mid)
		var vt: float = v.call(top)
		# lower band slightly darker: grime and bounce shadow near the ground
		_tri(st, A, B, Bm, Vector2(u0, vb), Vector2(u1, vb), Vector2(u1, vm), n, dark)
		_tri(st, A, Bm, Am, Vector2(u0, vb), Vector2(u1, vm), Vector2(u0, vm), n, dark)
		_tri(st, Am, Bm, Bt, Vector2(u0, vm), Vector2(u1, vm), Vector2(u1, vt), n, tint)
		_tri(st, Am, Bt, At, Vector2(u0, vm), Vector2(u1, vt), Vector2(u0, vt), n, tint)


# ---------------------------------------------------------------- trees

## Tree species: bark, leaf card texture, height range, crown shape.
const TREES := {
	"birch": {"bark": "bark_birch", "leaves": "leaves_birch", "h": [9.0, 15.0], "r": 0.16, "chance": 0.5},
	"broad": {"bark": "bark_pine", "leaves": "leaves_broad", "h": [8.0, 13.0], "r": 0.22, "chance": 0.2},
	"pine": {"bark": "bark_pine", "leaves": "needles", "h": [12.0, 20.0], "r": 0.25, "chance": 0.3},
}
const TREE_VARIANTS := 3


func _foliage_mat(tex: String) -> StandardMaterial3D:
	return mat("leaves_" + tex, "", {
		"albedo_texture": load(TEX + "foliage/" + tex + ".png"),
		"transparency": BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR, "alpha_scissor_threshold": 0.45,
		"alpha_antialiasing_mode": BaseMaterial3D.ALPHA_ANTIALIASING_ALPHA_TO_COVERAGE,
		"cull_mode": BaseMaterial3D.CULL_DISABLED, "roughness": 0.85,
		"backlight_enabled": true, "backlight": Color(0.35, 0.42, 0.2)})


## Tapered, slightly bent cylinder from a to b.
func _limb(st: SurfaceTool, a: Vector3, b: Vector3, r0: float, r1: float, sides: int, v_scale: float) -> void:
	var f := (b - a).normalized()
	var side := f.cross(Vector3.UP if absf(f.y) < 0.95 else Vector3.RIGHT).normalized()
	var up := side.cross(f).normalized()
	var len := a.distance_to(b)
	for k in sides:
		var a0 := TAU * k / sides
		var a1 := TAU * (k + 1) / sides
		var d0 := side * cos(a0) + up * sin(a0)
		var d1 := side * cos(a1) + up * sin(a1)
		var u0 := float(k) / sides
		var u1 := float(k + 1) / sides
		_quad(st, a + d0 * r0, a + d1 * r0, b + d1 * r1, b + d0 * r1,
			Vector2(u0, 0), Vector2(u1, 0), Vector2(u1, -len / v_scale), Vector2(u0, -len / v_scale), (d0 + d1).normalized())


## A leaf card: bottom centre at p, growing along dir, normals bent away from the crown centre.
func _leaf_card(st: SurfaceTool, p: Vector3, dir: Vector3, size: float, crown: Vector3, spin: float) -> void:
	var side := dir.cross(Vector3.UP if absf(dir.y) < 0.95 else Vector3.RIGHT).normalized().rotated(dir, spin) * size * 0.5
	var tip := dir * size
	var corners := [p - side, p + side, p + side + tip, p - side + tip]
	var uvs := [Vector2(0, 1), Vector2(1, 1), Vector2(1, 0), Vector2(0, 0)]
	for t in [[0, 1, 2], [0, 2, 3]]:
		for k in t:
			var c: Vector3 = corners[k]
			st.set_normal((c - crown).normalized())
			st.set_uv(uvs[k])
			st.set_color(Color.WHITE)
			st.add_vertex(c)


func _make_tree(kind: String, rng: RandomNumberGenerator) -> ArrayMesh:
	var spec: Dictionary = TREES[kind]
	var bark := SurfaceTool.new(); bark.begin(Mesh.PRIMITIVE_TRIANGLES)
	var leaves := SurfaceTool.new(); leaves.begin(Mesh.PRIMITIVE_TRIANGLES)
	var h := 1.0                       # built at unit height, scaled per instance
	var r: float = spec.r / 12.0
	var lean := Vector3(rng.randf_range(-0.04, 0.04), 0, rng.randf_range(-0.04, 0.04))
	var trunk := [Vector3.ZERO, Vector3(0, 0.35, 0) + lean * 0.5, Vector3(0, 0.7, 0) + lean, Vector3(0, h, 0) + lean * 1.4]
	for i in 3:
		_limb(bark, trunk[i] - Vector3(0, 0.02 if i == 0 else 0.0, 0), trunk[i + 1], r * (1.0 - i * 0.3), r * (0.7 - i * 0.3) + 0.002, 7, 0.12)
	if kind == "pine":
		var crown := Vector3(0, 0.72, 0) + lean
		var whorls := 9
		for w in whorls:
			var y := 0.4 + 0.6 * w / float(whorls)
			var base := Vector3(0, y, 0) + lean * y
			var len := 0.26 * (1.0 - (y - 0.4) / 0.62) + 0.04
			for b in 5:
				var ang := TAU * b / 5.0 + w * 0.9 + rng.randf() * 0.5
				var dir := Vector3(cos(ang), rng.randf_range(-0.25, 0.05), sin(ang)).normalized()
				_limb(bark, base, base + dir * len, 0.004, 0.0015, 4, 0.05)
				# needles: a flat card along the branch plus a tilted one
				_leaf_card(leaves, base, dir, len * 1.05, crown, 0.0)
				_leaf_card(leaves, base, dir, len * 1.05, crown, PI * 0.5)
		_leaf_card(leaves, Vector3(0, 0.93, 0) + lean * 1.3, Vector3.UP, 0.1, crown, 0.0)
	else:
		var crown := Vector3(0, 0.68, 0) + lean
		var branches := 14 if kind == "birch" else 18
		for b in branches:
			var y := rng.randf_range(0.35, 0.92)
			var base := Vector3(0, y, 0) + lean * y
			var ang := rng.randf() * TAU
			var up_t := rng.randf_range(0.5, 1.1) if kind == "birch" else rng.randf_range(0.3, 0.8)
			var dir := Vector3(cos(ang), up_t, sin(ang)).normalized()
			var len := rng.randf_range(0.14, 0.26) * (1.15 - absf(y - 0.62))
			var end := base + dir * len
			_limb(bark, base, end, 0.006, 0.002, 4, 0.05)
			for c in 4:
				var t := rng.randf_range(0.35, 1.0)
				var p := base.lerp(end, t)
				var cd := (dir + Vector3(rng.randf_range(-0.6, 0.6), rng.randf_range(-0.6, 0.3), rng.randf_range(-0.6, 0.6))).normalized()
				_leaf_card(leaves, p - cd * 0.03, cd, rng.randf_range(0.14, 0.2), crown, rng.randf() * PI)
	var m := bark.commit()
	m.surface_set_material(0, mat("bark_" + spec.bark, "", {"albedo_texture": load(TEX + "foliage/" + spec.bark + ".jpg"), "roughness": 0.95}))
	leaves.commit(m)
	m.surface_set_material(1, _foliage_mat(spec.leaves))
	return m


func _build_trees() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 9
	var kinds := TREES.keys()
	var buckets := {}
	for p in data.props.tree:
		var roll := rng.randf()
		var kind: String = kinds[-1]
		for k in kinds:
			roll -= TREES[k].chance
			if roll <= 0.0:
				kind = k
				break
		var key := "%s_%d" % [kind, rng.randi() % TREE_VARIANTS]
		if not buckets.has(key):
			buckets[key] = []
		buckets[key].append(p)
	for key in buckets:
		var kind: String = key.rsplit("_", true, 1)[0]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.mesh = _make_tree(kind, rng)
		mm.instance_count = buckets[key].size()
		for i in buckets[key].size():
			var p: Array = buckets[key][i]
			var h := rng.randf_range(TREES[kind].h[0], TREES[kind].h[1])
			var w := h * rng.randf_range(0.85, 1.15)
			var basis := Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3(w, h, w))
			mm.set_instance_transform(i, Transform3D(basis, Vector3(p[0], height_at(p[0], p[1]) - 0.1, p[1])))
			var s := rng.randf_range(0.85, 1.1)
			mm.set_instance_color(i, Color(s * rng.randf_range(0.95, 1.08), s, s * rng.randf_range(0.85, 1.0)))
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "Trees_" + key
		mmi.multimesh = mm
		add_child(mmi)


# ---------------------------------------------------------------- props and rails

func _build_props() -> void:
	var st := SurfaceTool.new(); st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var wood := Color(0.55, 0.36, 0.22)
	var metal := Color(0.25, 0.27, 0.3)
	var benches: Array = data.props.bench.duplicate()
	benches.append_array(_yard_benches())
	for b in benches:
		var c := Vector2(b[0], b[1])
		var d := Vector2(sin(b[2]), cos(b[2]))
		var s := Vector2(-d.y, d.x)
		var a2 := c - d * 0.9
		var b2 := c + d * 0.9
		var ya := height_at(a2.x, a2.y)
		var yb := height_at(b2.x, b2.y)
		var y := maxf(ya, yb)
		var A := Vector3(a2.x, y + BENCH_HEIGHT - 0.04, a2.y)
		var B := Vector3(b2.x, y + BENCH_HEIGHT - 0.04, b2.y)
		_beam(st, A, B, 0.45, 0.08, wood)
		var back := Vector3(s.x, 0, s.y) * 0.22
		_beam(st, A + back + Vector3(0, 0.35, 0), B + back + Vector3(0, 0.35, 0), 0.06, 0.25, wood)
		for e: Vector2 in [a2.lerp(b2, 0.1), a2.lerp(b2, 0.9)]:
			_beam(st, Vector3(e.x, y - 0.3, e.y), Vector3(e.x, y + BENCH_HEIGHT - 0.08, e.y), 0.08, 0.4, metal)
		_add_rail(PackedVector3Array([A + Vector3(0, 0.04, 0), B + Vector3(0, 0.04, 0)]), "Bench Grind")
	for p in data.props.lamp + _street_lamps():
		var g := ground(Vector2(p[0], p[1]))
		_beam(st, g - Vector3(0, 0.3, 0), g + Vector3(0, 8, 0), 0.18, 0.18, Color(0.45, 0.47, 0.5))
		var dir := Vector3(p[2], 0, p[3]) if p.size() > 3 else Vector3.RIGHT
		_beam(st, g + Vector3(0, 7.9, 0), g + Vector3(0, 7.9, 0) + dir * 1.6, 0.12, 0.12, Color(0.45, 0.47, 0.5))
		_beam(st, g + Vector3(0, 7.75, 0) + dir * 1.3, g + Vector3(0, 7.75, 0) + dir * 1.8, 0.3, 0.15, Color(1.0, 0.95, 0.7))
	for b in data.props.bus_stop:
		var c := Vector2(b[0], b[1])
		var d := Vector2(sin(b[2]), cos(b[2]))
		var g := ground(c)
		var D := Vector3(d.x, 0, d.y)
		var S := D.cross(Vector3.UP) * 0.8
		var blue := Color(0.3, 0.45, 0.65)
		_beam(st, g - D * 2.0 + S, g + D * 2.0 + S + Vector3(0, 0, 0), 0.1, 0.1, blue)
		for e: float in [-2.0, 2.0]:
			_beam(st, g + D * e - S, g + D * e - S + Vector3(0, 2.4, 0), 0.1, 0.1, blue)
			_beam(st, g + D * e + S, g + D * e + S + Vector3(0, 2.4, 0), 0.1, 0.1, blue)
		_beam(st, g - D * 2.1 + Vector3(0, 2.45, 0), g + D * 2.1 + Vector3(0, 2.45, 0), 1.9, 0.1, Color(0.7, 0.72, 0.75))
		_beam(st, g - D * 2.0 - S * 0.95 + Vector3(0, 1.2, 0), g + D * 2.0 - S * 0.95 + Vector3(0, 1.2, 0), 0.05, 2.2, Color(0.6, 0.75, 0.8))
	_add_mesh(st, mat("props", "", {"albedo_color": Color.WHITE}), true, "Props")


## Courtyard benches by the long walls of blocks of flats (OSM rarely maps them).
func _yard_benches() -> Array:
	var out := []
	for b in data.buildings:
		if not (b.k in ["panel", "khrush"]):
			continue
		var ring := _line(b.outer)
		var cw := _signed_area(ring) > 0.0
		for i in ring.size():
			var a := ring[i]
			var c := ring[(i + 1) % ring.size()]
			var len := a.distance_to(c)
			if len < 30.0:
				continue
			var d := (c - a) / len
			var n := Vector2(d.y, -d.x) if cw else Vector2(-d.y, d.x)
			var t := 8.0
			while t < len - 8.0:
				var p := a + d * t + n * 4.0
				if absf(p.x) < half - 2 and absf(p.y) < half - 2 and not _on_road(p, 1.0):
					out.append([p.x, p.y, atan2(d.x, d.y)])
				t += 26.0
	return out


## Lamp posts every ~35 m along the main roads, on alternating sides.
func _street_lamps() -> Array:
	var out := []
	for r in data.roads:
		if r.k != "road" or not (r.c in ["primary", "secondary", "tertiary"]):
			continue
		var pts := _resample(_line(r.p), 35.0)
		for i in pts.size() - 1:
			var t := (pts[i + 1] - pts[i]).normalized()
			var side := 1.0 if i % 2 == 0 else -1.0
			var n := Vector2(-t.y, t.x) * side
			var p := pts[i] + n * (float(r.w) * 0.5 + 1.0)
			if not _on_road(p, 0.5):
				out.append([p.x, p.y, -n.x, -n.y])
	return out


func _add_handrails(pts: PackedVector2Array, w: float) -> void:
	pts = _resample(pts, 1.0)
	if pts.size() < 3:
		return
	var st := SurfaceTool.new(); st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var col := Color(0.72, 0.2, 0.16)
	for side: float in [-1.0, 1.0]:
		var run := PackedVector3Array()
		for i in pts.size():
			var t := (pts[mini(i + 1, pts.size() - 1)] - pts[maxi(i - 1, 0)]).normalized()
			run.append(ground(pts[i] + Vector2(-t.y, t.x) * side * (w * 0.5 + 0.1), HANDRAIL_HEIGHT))
		for i in run.size() - 1:
			_beam(st, run[i], run[i + 1], 0.06, 0.06, col)
		for i in range(0, run.size(), 2):
			_beam(st, run[i] - Vector3(0, HANDRAIL_HEIGHT + 0.1, 0), run[i], 0.05, 0.05, col)
		_add_rail(run, "Handrail Grind")
	_add_mesh(st, mat("handrail", "", {"albedo_color": Color.WHITE}), false, "Handrail")


func _build_rails() -> void:
	for l in data.ledges:
		var run := PackedVector3Array()
		for p in _resample(_line(l.p), 1.0):
			run.append(ground(p, 0.5))
		_add_rail(run, "Ledge Grind")


func _add_rail(pts: PackedVector3Array, rail_name: String) -> void:
	if pts.size() < 2:
		return
	var idx := rails.size()
	rails.append({"pts": pts, "name": rail_name})
	for i in pts.size() - 1:
		var key := _cell(Vector2(pts[i].x, pts[i].z).lerp(Vector2(pts[i + 1].x, pts[i + 1].z), 0.5), 4.0)
		if not rail_grid.has(key):
			rail_grid[key] = []
		rail_grid[key].append(Vector2i(idx, i))


## Rail segments near a point: Array of Vector2i(rail, segment).
func rails_near(p: Vector3) -> Array:
	var out := []
	var c := _cell(Vector2(p.x, p.z), 4.0)
	for dx in range(-1, 2):
		for dz in range(-1, 2):
			out.append_array(rail_grid.get(c + Vector2i(dx, dz), []))
	return out


func _collect_spawns() -> void:
	var sp: Dictionary = data.spawn
	spawn_points.append({"p": ground(_v2(sp.p), 0.3), "yaw": float(sp.yaw), "name": "Лестница на Высоцкого"})
	for s in data.spots:
		if s.kind == "stairs":
			spawn_points.append({"p": ground(_v2(s.p), 0.3) + Vector3(0, 0, 0), "yaw": 0.0, "name": "Лестница"})
	spawn_points.append({"p": ground(Vector2(0, 0), 0.3), "yaw": 0.0, "name": "Центр куска"})
