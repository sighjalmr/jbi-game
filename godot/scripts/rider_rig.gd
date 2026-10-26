extends Node3D
class_name RiderRig
## The rider: a skinned, low-poly person built in code (skeleton + mesh), animated procedurally.
## Poses are layered from simple rules (walk cycle, skate stance, BMX on the pedals) and
## two-bone IK for feet and hands; bones ease towards their targets every frame.
## Model space: Y up, the rider faces +Z, their left is +X, feet at y = 0.

const BONES := [
	# name, parent, rest position in model space
	["hips", "", Vector3(0, 0.95, 0)],
	["spine", "hips", Vector3(0, 1.07, 0)],
	["chest", "spine", Vector3(0, 1.27, 0)],
	["neck", "chest", Vector3(0, 1.47, 0)],
	["head", "neck", Vector3(0, 1.56, 0)],
	["upperarm.L", "chest", Vector3(0.19, 1.43, 0)],
	["forearm.L", "upperarm.L", Vector3(0.19, 1.16, 0)],
	["hand.L", "forearm.L", Vector3(0.19, 0.91, 0)],
	["upperarm.R", "chest", Vector3(-0.19, 1.43, 0)],
	["forearm.R", "upperarm.R", Vector3(-0.19, 1.16, 0)],
	["hand.R", "forearm.R", Vector3(-0.19, 0.91, 0)],
	["thigh.L", "hips", Vector3(0.1, 0.92, 0)],
	["shin.L", "thigh.L", Vector3(0.1, 0.5, 0)],
	["foot.L", "shin.L", Vector3(0.1, 0.08, 0)],
	["thigh.R", "hips", Vector3(-0.1, 0.92, 0)],
	["shin.R", "thigh.R", Vector3(-0.1, 0.5, 0)],
	["foot.R", "shin.R", Vector3(-0.1, 0.08, 0)],
]
const LEG := [0.42, 0.42]
const ARM := [0.27, 0.25]

@export var hoodie := Color(0.2, 0.42, 0.3)
@export var jeans := Color(0.2, 0.26, 0.42)
@export var skin := Color(0.9, 0.72, 0.58)
@export var shoes := Color(0.93, 0.93, 0.9)
@export var beanie := Color(0.12, 0.12, 0.14)

var skeleton: Skeleton3D
var _idx := {}
var _parent: Array[int] = []
var _offset: Array[Vector3] = []     # rest offset from the parent joint
var _cur: Array[Quaternion] = []
var _cur_hips := Vector3.ZERO

# pose being built this frame
var _q: Array[Quaternion] = []
var _hips := Vector3.ZERO


func _ready() -> void:
	skeleton = Skeleton3D.new()
	skeleton.name = "Skeleton"
	add_child(skeleton)
	for b in BONES:
		var i := skeleton.add_bone(b[0])
		_idx[b[0]] = i
		var p: int = _idx[b[1]] if b[1] != "" else -1
		_parent.append(p)
		if p >= 0:
			skeleton.set_bone_parent(i, p)
		var off: Vector3 = b[2] - (BONES[p][2] if p >= 0 else Vector3.ZERO)
		_offset.append(off)
		skeleton.set_bone_rest(i, Transform3D(Basis(), off))
		_cur.append(Quaternion.IDENTITY)
		_q.append(Quaternion.IDENTITY)
	skeleton.reset_bone_poses()
	var mi := MeshInstance3D.new()
	mi.name = "Body"
	mi.mesh = _build_mesh()
	skeleton.add_child(mi)
	mi.skeleton = NodePath("..")
	mi.skin = skeleton.create_skin_from_rest_transforms()


# ---------------------------------------------------------------- mesh

func _pos(name: String) -> Vector3:
	return BONES[_idx[name]][2]


## Elliptic tube between two joints, skinned to `bone`, blending into `parent` near the start.
func _tube(st: SurfaceTool, a: Vector3, b: Vector3, ra: Vector2, rb: Vector2, bone: String, parent: String, col: Color, blend := 0.06, rings := 5, seg := 10) -> void:
	var dir := (b - a).normalized()
	var side := (Vector3.RIGHT - dir * dir.dot(Vector3.RIGHT)).normalized()
	var other := dir.cross(side)
	var bi: int = _idx[bone]
	var pi: int = _idx[parent] if parent != "" else bi
	var len := a.distance_to(b)
	var base := _vcount
	for r in rings + 1:
		var t := float(r) / rings
		var c := a.lerp(b, t)
		var rad := ra.lerp(rb, t)
		# rounded ends
		var cap := sin(clampf(t * 6.0, 0.0, 1.0) * PI * 0.5) * sin(clampf((1.0 - t) * 6.0, 0.0, 1.0) * PI * 0.5)
		rad *= 0.55 + 0.45 * cap
		var w := smoothstep(0.0, blend, t * len)
		for s in seg:
			var ang := TAU * s / seg
			var n := side * cos(ang) * rad.y + other * sin(ang) * rad.x
			var off := side * cos(ang) * rad.x + other * sin(ang) * rad.y
			st.set_color(col)
			st.set_normal(n.normalized())
			st.set_bones(PackedInt32Array([bi, pi, 0, 0]))
			st.set_weights(PackedFloat32Array([w, 1.0 - w, 0, 0]))
			st.add_vertex(c + off)
			_vcount += 1
	for r in rings:
		for s in seg:
			var i0 := base + r * seg + s
			var i1 := base + r * seg + (s + 1) % seg
			st.add_index(i0); st.add_index(i1 + seg); st.add_index(i1)
			st.add_index(i0); st.add_index(i0 + seg); st.add_index(i1 + seg)
	# end caps
	for end: int in [0, rings]:
		var ring0 := base + end * seg
		for s in range(1, seg - 1):
			if end == 0:
				st.add_index(ring0); st.add_index(ring0 + s); st.add_index(ring0 + s + 1)
			else:
				st.add_index(ring0); st.add_index(ring0 + s + 1); st.add_index(ring0 + s)


## Ellipsoid on one bone (head); `paint` picks the colour per vertex.
func _blob(st: SurfaceTool, c: Vector3, r: Vector3, bone: String, paint: Callable) -> void:
	var bi: int = _idx[bone]
	var base := _vcount
	var rings := 10
	var seg := 14
	for i in rings + 1:
		var v := PI * i / rings
		for s in seg:
			var u := TAU * s / seg
			var n := Vector3(sin(v) * sin(u), cos(v), sin(v) * cos(u))
			var p := c + n * r
			st.set_color(paint.call(n))
			st.set_normal(n)
			st.set_bones(PackedInt32Array([bi, 0, 0, 0]))
			st.set_weights(PackedFloat32Array([1, 0, 0, 0]))
			st.add_vertex(p)
			_vcount += 1
	for i in rings:
		for s in seg:
			var a := base + i * seg + s
			var b := base + i * seg + (s + 1) % seg
			st.add_index(a); st.add_index(b); st.add_index(a + seg)
			st.add_index(b); st.add_index(b + seg); st.add_index(a + seg)


var _vcount := 0


func _build_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_vcount = 0
	# torso: jeans at the pelvis, hoodie above
	_tube(st, Vector3(0, 0.84, 0), Vector3(0, 1.08, 0), Vector2(0.165, 0.115), Vector2(0.155, 0.11), "hips", "", jeans)
	_tube(st, Vector3(0, 1.0, 0.0), Vector3(0, 1.28, 0.0), Vector2(0.165, 0.12), Vector2(0.18, 0.125), "spine", "hips", hoodie, 0.08)
	_tube(st, Vector3(0, 1.24, 0.0), Vector3(0, 1.5, -0.01), Vector2(0.19, 0.13), Vector2(0.14, 0.1), "chest", "spine", hoodie, 0.08)
	_tube(st, Vector3(0, 1.44, -0.06), Vector3(0, 1.56, -0.08), Vector2(0.11, 0.06), Vector2(0.09, 0.05), "chest", "", hoodie, 0.0, 3)   # hood
	_tube(st, Vector3(0, 1.45, 0), Vector3(0, 1.6, 0.01), Vector2(0.05, 0.05), Vector2(0.048, 0.048), "neck", "chest", skin, 0.04)
	_blob(st, Vector3(0, 1.67, 0.015), Vector3(0.105, 0.125, 0.115), "head", func(n: Vector3) -> Color:
		if n.y > 0.15 - n.z * 0.25:
			return beanie
		return skin)
	for side: float in [1.0, -1.0]:
		var s := "L" if side > 0 else "R"
		var x := 0.19 * side
		_tube(st, Vector3(x, 1.46, 0), Vector3(x, 1.15, 0), Vector2(0.06, 0.06), Vector2(0.05, 0.05), "upperarm." + s, "chest", hoodie, 0.05)
		_tube(st, Vector3(x, 1.18, 0), Vector3(x, 0.9, 0), Vector2(0.05, 0.05), Vector2(0.043, 0.043), "forearm." + s, "upperarm." + s, hoodie, 0.05)
		_tube(st, Vector3(x, 0.93, 0), Vector3(x, 0.78, 0.01), Vector2(0.03, 0.045), Vector2(0.025, 0.035), "hand." + s, "forearm." + s, skin, 0.03, 3, 8)
		var lx := 0.1 * side
		_tube(st, Vector3(lx, 0.96, 0), Vector3(lx, 0.49, 0), Vector2(0.088, 0.09), Vector2(0.062, 0.065), "thigh." + s, "hips", jeans, 0.08)
		_tube(st, Vector3(lx, 0.53, 0), Vector3(lx, 0.07, -0.01), Vector2(0.063, 0.065), Vector2(0.06, 0.06), "shin." + s, "thigh." + s, jeans, 0.06)
		_tube(st, Vector3(lx, 0.06, -0.07), Vector3(lx, 0.05, 0.19), Vector2(0.055, 0.05), Vector2(0.05, 0.035), "foot." + s, "shin." + s, shoes, 0.02, 4, 10)
	var m := st.commit()
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true
	mat.roughness = 0.85
	m.surface_set_material(0, mat)
	return m


# ---------------------------------------------------------------- pose building

func _rot(bone: String, euler: Vector3) -> void:
	_q[_idx[bone]] = Quaternion.from_euler(euler)


func _begin() -> void:
	for i in _q.size():
		_q[i] = Quaternion.IDENTITY
	_hips = Vector3.ZERO


## Model-space transform of every bone for the pose being built.
func _globals() -> Array[Transform3D]:
	var g: Array[Transform3D] = []
	for i in _q.size():
		var local := Transform3D(Basis(_q[i]), _offset[i] + (_hips if i == 0 else Vector3.ZERO))
		g.append(g[_parent[i]] * local if _parent[i] >= 0 else local)
	return g


## Two-bone IK: aims `upper` and `lower` so the end of the chain reaches `target` (model space).
## bend = +1 bends the middle joint forward (knee), -1 backward (elbow).
func _ik(upper: String, lower: String, end: String, target: Vector3, lens: Array, bend: float, keep_end_level := true) -> void:
	var g := _globals()
	var u: int = _idx[upper]
	var parent_g: Transform3D = g[_parent[u]]
	var t := parent_g.affine_inverse() * target - _offset[u]
	var l1: float = lens[0]
	var l2: float = lens[1]
	var d := clampf(t.length(), 0.05, l1 + l2 - 0.002)
	var dir := t.normalized()
	var cos_b := clampf((l1 * l1 + d * d - l2 * l2) / (2.0 * l1 * d), -1.0, 1.0)
	var beta := acos(cos_b)
	var axis := Vector3.RIGHT
	var up_dir := dir.rotated(axis, -bend * beta)
	var q1 := Quaternion(Vector3.DOWN, up_dir)
	var mid := up_dir * l1
	var w := (dir * d - mid).normalized()
	var q2 := Quaternion(Vector3.DOWN, q1.inverse() * w)
	_q[u] = q1
	_q[_idx[lower]] = q2
	if keep_end_level:
		var parent_rot := parent_g.basis.get_rotation_quaternion()
		_q[_idx[end]] = (parent_rot * q1 * q2).inverse()


func _apply(dt: float, rate: float) -> void:
	var a := 1.0 - exp(-rate * dt)
	for i in _q.size():
		_cur[i] = _cur[i].slerp(_q[i], a)
		skeleton.set_bone_pose_rotation(i, _cur[i])
	_cur_hips = _cur_hips.lerp(_hips, a)
	skeleton.set_bone_pose_position(0, _offset[0] + _cur_hips)


# ---------------------------------------------------------------- poses

## On foot: idle, walk and run. `phase` advances with distance travelled.
func pose_foot(dt: float, speed: float, phase: float, airborne: bool) -> void:
	_begin()
	var t := Time.get_ticks_msec() / 1000.0
	if airborne:
		_rot("thigh.L", Vector3(-0.9, 0, 0.05)); _rot("shin.L", Vector3(1.3, 0, 0))
		_rot("thigh.R", Vector3(-0.3, 0, -0.05)); _rot("shin.R", Vector3(0.6, 0, 0))
		_rot("upperarm.L", Vector3(-0.6, 0, 0.5)); _rot("upperarm.R", Vector3(0.4, 0, -0.5))
		_rot("forearm.L", Vector3(-0.8, 0, 0)); _rot("forearm.R", Vector3(-0.8, 0, 0))
		_rot("spine", Vector3(0.15, 0, 0))
		_apply(dt, 12.0)
		return
	var run := clampf((speed - 2.0) / 3.0, 0.0, 1.0)
	var amt := clampf(speed / 2.0, 0.0, 1.0)
	var s := sin(phase)
	var c := cos(phase)
	var swing := 0.45 + 0.35 * run
	_rot("thigh.L", Vector3(-s * swing * amt, 0, 0.03))
	_rot("thigh.R", Vector3(s * swing * amt, 0, -0.03))
	_rot("shin.L", Vector3((0.15 + (0.9 + 0.6 * run) * maxf(0.0, c)) * amt, 0, 0))
	_rot("shin.R", Vector3((0.15 + (0.9 + 0.6 * run) * maxf(0.0, -c)) * amt, 0, 0))
	_rot("foot.L", Vector3(s * 0.25 * amt, 0, 0)); _rot("foot.R", Vector3(-s * 0.25 * amt, 0, 0))
	var arm := (0.35 + 0.4 * run) * amt
	_rot("upperarm.L", Vector3(s * arm, 0, 0.08)); _rot("upperarm.R", Vector3(-s * arm, 0, -0.08))
	_rot("forearm.L", Vector3(-0.25 - 0.9 * run * amt, 0, 0)); _rot("forearm.R", Vector3(-0.25 - 0.9 * run * amt, 0, 0))
	_rot("spine", Vector3(0.04 + 0.18 * run * amt, s * 0.12 * amt, 0))
	_rot("chest", Vector3(0.0, -s * 0.15 * amt, 0))
	_rot("hips", Vector3(0, s * 0.08 * amt, 0))
	_hips = Vector3(0, -absf(c) * 0.04 * amt - 0.04 * run, 0)
	if amt < 0.05:   # idle: breathing and a slight weight shift
		_rot("chest", Vector3(sin(t * 1.6) * 0.02, 0, 0))
		_rot("upperarm.L", Vector3(0, 0, 0.08)); _rot("upperarm.R", Vector3(0, 0, -0.08))
		_rot("hips", Vector3(0, 0, sin(t * 0.7) * 0.03))
	_apply(dt, 14.0)


## Sideways on the board. Board axis is the rig's X (the rig is turned 90° by the caller),
## the nose is at -X. crouch 0..1, push_phase drives the back foot while pushing.
func pose_skate(dt: float, crouch: float, pushing: bool, push_phase: float, steer: float, grab: bool, grind_balance: float, airborne: bool, board_y: float) -> void:
	_begin()
	crouch = clampf(crouch, 0.0, 1.0)
	var feet_y := board_y + 0.07
	var leg_drop := 0.08 + 0.32 * crouch
	_hips = Vector3(0, -leg_drop + board_y, -0.02 - 0.06 * crouch)
	_rot("hips", Vector3(0, 0.25, steer * 0.12))
	_rot("spine", Vector3(0.12 + 0.25 * crouch + grind_balance * 0.5, 0.15, steer * 0.15))
	_rot("chest", Vector3(0.05, 0.2, 0))
	_rot("neck", Vector3(0, -0.5, 0))
	_rot("head", Vector3(0.1, -0.75, 0))
	var arms := 0.35 + 0.5 * crouch + absf(grind_balance) * 0.6
	_rot("upperarm.L", Vector3(-0.15, 0, arms + 0.2)); _rot("forearm.L", Vector3(-0.5, 0, 0))
	_rot("upperarm.R", Vector3(-0.25, 0, -arms)); _rot("forearm.R", Vector3(-0.5, 0, 0))
	var front := Vector3(-0.27, feet_y, 0.04)
	var back := Vector3(0.24, feet_y, 0.02)
	if pushing:
		# back foot steps off and kicks along the ground beside the board
		var k := sin(push_phase)
		back = Vector3(0.25 + k * 0.38, 0.07 + maxf(0.0, -cos(push_phase)) * 0.1, 0.24)
		_hips.y -= 0.06
		_rot("spine", Vector3(0.35, 0.1, 0))
	if grab:
		_rot("upperarm.R", Vector3(-0.9, 0, -0.3)); _rot("forearm.R", Vector3(-0.2, 0, 0))
		_rot("spine", Vector3(0.6, 0.1, 0))
	_ik("thigh.R", "shin.R", "foot.R", front, LEG, 1.0)
	_ik("thigh.L", "shin.L", "foot.L", back, LEG, 1.0)
	_apply(dt, 30.0 if pushing or airborne else 16.0)


## Standing on the pedals of the BMX; hands on the grips. `bike` gives the pedal and grip positions.
func pose_bmx(dt: float, bike: BmxBike, crouch: float, steer: float, trick: String, trick_k: float) -> void:
	_begin()
	_hips = Vector3(0, -0.14 - 0.12 * crouch, -0.2)
	_rot("spine", Vector3(0.5 + 0.2 * crouch, 0, steer * 0.1))
	_rot("chest", Vector3(0.2, 0, 0))
	_rot("head", Vector3(-0.35, 0, 0))
	var grips := bike.grips()
	var pedals := bike.pedals()
	match trick:
		"Superman":
			_hips = Vector3(0, 0.1, -0.35)
			_rot("spine", Vector3(1.2, 0, 0))
			_rot("head", Vector3(-0.9, 0, 0))
			_rot("thigh.L", Vector3(0.9, 0, 0.1)); _rot("thigh.R", Vector3(0.8, 0, -0.1))
			_rot("shin.L", Vector3(0.2, 0, 0)); _rot("shin.R", Vector3(0.3, 0, 0))
			_ik("upperarm.L", "forearm.L", "hand.L", grips[0], ARM, -1.0, false)
			_ik("upperarm.R", "forearm.R", "hand.R", grips[1], ARM, -1.0, false)
			_apply(dt, 14.0)
			return
		"Barspin":
			# let go while the bars spin, hands up and back
			var free := sin(clampf(trick_k, 0.0, 1.0) * PI)
			_ik("thigh.L", "shin.L", "foot.L", pedals[0], LEG, 1.0)
			_ik("thigh.R", "shin.R", "foot.R", pedals[1], LEG, 1.0)
			_ik("upperarm.L", "forearm.L", "hand.L", grips[0] + Vector3(0.15, 0.25, -0.2) * free, ARM, -1.0, false)
			_ik("upperarm.R", "forearm.R", "hand.R", grips[1] + Vector3(-0.15, 0.25, -0.2) * free, ARM, -1.0, false)
			_apply(dt, 30.0)
			return
		"Tailwhip":
			# feet off while the frame whips round
			_ik("upperarm.L", "forearm.L", "hand.L", grips[0], ARM, -1.0, false)
			_ik("upperarm.R", "forearm.R", "hand.R", grips[1], ARM, -1.0, false)
			_rot("thigh.L", Vector3(-0.4, 0, 0.35)); _rot("thigh.R", Vector3(-0.4, 0, -0.35))
			_rot("shin.L", Vector3(1.1, 0, 0)); _rot("shin.R", Vector3(1.1, 0, 0))
			_hips.y += 0.12
			_apply(dt, 20.0)
			return
	_ik("thigh.L", "shin.L", "foot.L", pedals[0], LEG, 1.0)
	_ik("thigh.R", "shin.R", "foot.R", pedals[1], LEG, 1.0)
	_ik("upperarm.L", "forearm.L", "hand.L", grips[0], ARM, -1.0, false)
	_ik("upperarm.R", "forearm.R", "hand.R", grips[1], ARM, -1.0, false)
	_apply(dt, 40.0)


## Thrown off: limbs flail, the caller tumbles the whole rig.
func pose_bail(dt: float, k: float) -> void:
	_begin()
	_rot("upperarm.L", Vector3(-1.2 + sin(k * 9.0) * 0.4, 0, 1.0))
	_rot("upperarm.R", Vector3(-1.4 + cos(k * 8.0) * 0.4, 0, -1.0))
	_rot("forearm.L", Vector3(-0.6, 0, 0)); _rot("forearm.R", Vector3(-0.5, 0, 0))
	_rot("thigh.L", Vector3(-0.8, 0, 0.3)); _rot("shin.L", Vector3(0.9, 0, 0))
	_rot("thigh.R", Vector3(-0.2, 0, -0.2)); _rot("shin.R", Vector3(0.4, 0, 0))
	_rot("spine", Vector3(-0.3, 0, 0))
	_rot("head", Vector3(-0.4, 0, 0))
	_apply(dt, 10.0)
