extends Node3D
class_name MixamoBody
## A ready-made character (a Mixamo FBX/GLB dropped into res://characters/) worn over the
## procedural RiderRig: every frame the rig's bone rotations are copied onto the Mixamo
## skeleton. The rig's own mesh is hidden and its joints are refitted to this body, so the
## IK (feet on the board and pedals, hands on the grips) lands on the real limbs.
## Model files are not in git (Mixamo assets can't be redistributed).

const DIR := "res://characters"
const MAP := {
	"hips": "Hips", "spine": "Spine", "chest": "Spine2", "neck": "Neck", "head": "Head",
	"upperarm.L": "LeftArm", "forearm.L": "LeftForeArm", "hand.L": "LeftHand",
	"upperarm.R": "RightArm", "forearm.R": "RightForeArm", "hand.R": "RightHand",
	"thigh.L": "LeftUpLeg", "shin.L": "LeftLeg", "foot.L": "LeftFoot",
	"thigh.R": "RightUpLeg", "shin.R": "RightLeg", "foot.R": "RightFoot",
}
# limbs hang straight down on the rig, but stick out in a T on the Mixamo rest pose
const ALIGN := {
	"LeftArm": "LeftForeArm", "LeftForeArm": "LeftHand", "LeftHand": "LeftHandMiddle1",
	"RightArm": "RightForeArm", "RightForeArm": "RightHand", "RightHand": "RightHandMiddle1",
	"LeftUpLeg": "LeftLeg", "LeftLeg": "LeftFoot", "RightUpLeg": "RightLeg", "RightLeg": "RightFoot",
}
const FINGER_CURL := 0.28

var skel: Skeleton3D
var _by_name := {}                 # Mixamo name without prefix -> bone index
var _src := PackedInt32Array()     # per Mixamo bone: rig bone index or -1
var _rest_g: Array[Quaternion] = []   # Mixamo rest, model space
var _aligned: Array[Quaternion] = []  # Mixamo rest with the limbs hanging down
var _local: Array[Quaternion] = []    # Mixamo local rest (unmapped bones keep it)
var _curl: Array[Quaternion] = []     # finger curl, model space at rest
var _rest_hips := Vector3.ZERO
var _rig: RiderRig


## Path of the first character model in res://characters, or "".
static func find_model() -> String:
	var d := DirAccess.open(DIR)
	if d == null:
		return ""
	for f in d.get_files():
		var e := f.get_extension().to_lower()
		if e in ["fbx", "glb", "gltf"]:
			return DIR.path_join(f)
	return ""


## Loads the model and reads its skeleton. Returns false if it isn't a Mixamo-style rig.
func load_model(path: String) -> bool:
	var ps := load(path) as PackedScene
	if ps == null:
		return false
	var scene := ps.instantiate()
	add_child(scene)
	for ap in scene.find_children("*", "AnimationPlayer", true, false):
		ap.queue_free()
	var found := scene.find_children("*", "Skeleton3D", true, false)
	if found.is_empty():
		return false
	skel = found[0]
	var re := RegEx.create_from_string("^mixamorig\\d*[:_]")
	for i in skel.get_bone_count():
		_by_name[re.sub(skel.get_bone_name(i), "")] = i
	for v: String in MAP.values():
		if not _by_name.has(v):
			return false
	_fix_materials(scene)
	return true


## Joint positions for RiderRig.fit(), in the rig's model space.
func joints() -> Dictionary:
	var out := {}
	for k: String in MAP:
		out[k] = _rest_pos(MAP[k])
	return out


func _rest_pos(n: String) -> Vector3:
	return skel.get_bone_global_rest(_by_name[n]).origin


## Hooks up to the rig (after both are in the tree) and precomputes the rest alignment.
func bind(rig: RiderRig) -> void:
	_rig = rig
	var n := skel.get_bone_count()
	_src.resize(n)
	_src.fill(-1)
	for k: String in MAP:
		_src[_by_name[MAP[k]]] = rig.skeleton.find_bone(k)
	_rest_hips = skel.get_bone_rest(_by_name["Hips"]).origin
	var re := RegEx.create_from_string("^mixamorig\\d*[:_]")
	for i in n:
		var g := skel.get_bone_global_rest(i).basis.get_rotation_quaternion()
		_rest_g.append(g)
		_local.append(skel.get_bone_rest(i).basis.get_rotation_quaternion())
		var name := re.sub(skel.get_bone_name(i), "")
		var a := g
		var p := skel.get_bone_parent(i)
		if not MAP.values().has(name) and p >= 0:
			a = _aligned[p] * _local[i]
		if ALIGN.has(name):
			var from := (_rest_pos(ALIGN[name]) - _rest_pos(name)).normalized()
			a = Quaternion(from, Vector3.DOWN) * g
		_aligned.append(a)
		# fingers curl in towards the palm (palms face down on the T pose, fingers along ±X)
		var c := Quaternion.IDENTITY
		if name.contains("Hand") and name != "LeftHand" and name != "RightHand":
			var side := 1.0 if name.begins_with("Left") else -1.0
			var amt := FINGER_CURL * (0.4 if name.contains("Thumb") else 1.0)
			c = Quaternion(Vector3(0, 0, -side), amt)
		_curl.append(c)


func _process(_dt: float) -> void:
	if _rig == null:
		return
	var rs := _rig.skeleton
	var n := skel.get_bone_count()
	var glob: Array[Quaternion] = []
	glob.resize(n)
	for i in n:
		var p := skel.get_bone_parent(i)
		var s := _src[i]
		var g: Quaternion
		if s >= 0:
			# the rig's bones rest with no rotation, so its global pose is the change from rest
			g = rs.get_bone_global_pose(s).basis.get_rotation_quaternion() * _aligned[i]
		elif p >= 0:
			# follow the parent as on the (aligned) rest pose, plus finger curl
			var delta := glob[p] * _aligned[p].inverse()
			g = delta * _curl[i] * _aligned[i]
		else:
			g = _rest_g[i]
		glob[i] = g
		var local := (glob[p].inverse() * g) if p >= 0 else g
		skel.set_bone_pose_rotation(i, local.normalized())
	var hips := rs.get_bone_pose_position(0) - rs.get_bone_rest(0).origin
	skel.set_bone_pose_position(_by_name["Hips"], _rest_hips + hips)


## Mixamo exports come in with plain materials; give hair alpha and the body some sheen.
func _fix_materials(scene: Node) -> void:
	for mi: MeshInstance3D in scene.find_children("*", "MeshInstance3D", true, false):
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i) as StandardMaterial3D
			if m == null:
				continue
			m = m.duplicate()
			var hair := mi.name.to_lower().contains("hair") or mi.name.to_lower().contains("lash") or m.resource_name.to_lower().contains("hair")
			if hair:
				m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS
				m.cull_mode = BaseMaterial3D.CULL_DISABLED
			m.metallic = 0.0
			mi.set_surface_override_material(i, m)
