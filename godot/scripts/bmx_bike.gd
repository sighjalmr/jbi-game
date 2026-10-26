extends Node3D
class_name BmxBike
## A 20" BMX built from primitives. +Z is forward, origin on the ground between the wheels.
## Front end (bars, fork, front wheel) and the frame both pivot on the head tube, so
## barspins and tailwhips are just rotations of those two parts.

const WHEEL_R := 0.255
const REAR_AXLE := Vector3(0, WHEEL_R, -0.48)
const FRONT_AXLE := Vector3(0, WHEEL_R, 0.5)
const BB := Vector3(0, 0.3, -0.04)
const CRANK := 0.175
const HEAD_TOP := Vector3(0, 0.8, 0.32)
const HEAD_BOT := Vector3(0, 0.6, 0.38)

@export var frame_color := Color(0.85, 0.22, 0.1)

var crank_angle := 0.0
var bar_angle := 0.0        # barspin
var whip_angle := 0.0       # tailwhip
var front: Node3D           # pivots on the head tube
var frame: Node3D           # pivots on the head tube
var crank: Node3D
var _wheels: Array[Node3D] = []
var _axis := Vector3.ZERO
var _metal: StandardMaterial3D
var _paint: StandardMaterial3D
var _rubber: StandardMaterial3D


func _ready() -> void:
	_axis = (HEAD_TOP - HEAD_BOT).normalized()
	_paint = _material(frame_color, 0.35, 0.4)
	_metal = _material(Color(0.75, 0.76, 0.78), 0.3, 0.9)
	_rubber = _material(Color(0.08, 0.08, 0.08), 0.9, 0.0)

	frame = Node3D.new()
	frame.name = "Frame"
	frame.position = HEAD_BOT
	add_child(frame)
	var o := -HEAD_BOT    # frame parts are placed in bike space, shifted to the pivot
	var seat_top := Vector3(0, 0.74, -0.22)
	_tube(frame, HEAD_TOP + o, seat_top + o, 0.022, _paint)          # top tube
	_tube(frame, HEAD_BOT + o, BB + o, 0.026, _paint)                # down tube
	_tube(frame, seat_top + o, BB + o, 0.022, _paint)                # seat tube
	for x: float in [-0.06, 0.06]:
		_tube(frame, BB + o + Vector3(x, 0, 0), REAR_AXLE + o + Vector3(x, 0, 0), 0.014, _paint)      # chain stays
		_tube(frame, seat_top + o + Vector3(x * 0.5, -0.04, 0), REAR_AXLE + o + Vector3(x, 0, 0), 0.012, _paint)
	_tube(frame, HEAD_BOT + o, HEAD_TOP + o, 0.03, _paint)           # head tube
	_tube(frame, seat_top + o + Vector3(0, -0.05, 0), seat_top + o + Vector3(0, 0.08, 0.02), 0.014, _metal)
	_box(frame, Vector3(0.11, 0.05, 0.24), seat_top + o + Vector3(0, 0.09, 0.0), _rubber)                  # seat
	_wheels.append(_wheel(frame, REAR_AXLE + o))
	for x: float in [-0.09, 0.09]:
		_tube(frame, REAR_AXLE + o + Vector3(x, 0, 0), REAR_AXLE + o + Vector3(x * 1.9, 0, 0), 0.02, _metal)   # pegs
	crank = Node3D.new()
	crank.position = BB + o
	frame.add_child(crank)
	_tube(crank, Vector3(0.07, 0, 0), Vector3(0.07, 0, CRANK), 0.012, _metal)
	_tube(crank, Vector3(-0.07, 0, 0), Vector3(-0.07, 0, -CRANK), 0.012, _metal)
	_tube(crank, Vector3(-0.08, 0, 0), Vector3(0.08, 0, 0), 0.015, _metal)
	_box(crank, Vector3(0.1, 0.02, 0.08), Vector3(0.13, 0, CRANK), _rubber)
	_box(crank, Vector3(0.1, 0.02, 0.08), Vector3(-0.13, 0, -CRANK), _rubber)
	_tube(crank, Vector3(0.03, 0, 0), Vector3(0.03, 0.001, 0.001), 0.06, _metal)   # sprocket

	front = Node3D.new()
	front.name = "Front"
	front.position = HEAD_BOT
	add_child(front)
	for x: float in [-0.05, 0.05]:
		_tube(front, Vector3(x, 0.02, 0) + (HEAD_BOT - HEAD_BOT), FRONT_AXLE - HEAD_BOT + Vector3(x, 0, 0), 0.016, _metal)   # fork legs
	var stem := HEAD_TOP - HEAD_BOT + _axis * 0.06
	_tube(front, Vector3.ZERO, stem, 0.018, _metal)
	var bar_mid := stem + Vector3(0, 0.12, -0.03)
	for x: float in [-1.0, 1.0]:
		_tube(front, stem + Vector3(0.04 * x, 0, 0), bar_mid + Vector3(0.12 * x, 0, 0), 0.012, _metal)
		_tube(front, bar_mid + Vector3(0.12 * x, 0, 0), bar_mid + Vector3(0.32 * x, 0.02, -0.02), 0.012, _metal)
		_tube(front, bar_mid + Vector3(0.24 * x, 0.01, -0.01), bar_mid + Vector3(0.33 * x, 0.02, -0.02), 0.018, _rubber)   # grips
	_tube(front, bar_mid + Vector3(-0.12, 0, 0), bar_mid + Vector3(0.12, 0, 0), 0.012, _metal)
	_tube(front, stem + Vector3(-0.1, 0.02, 0), stem + Vector3(0.1, 0.02, 0), 0.01, _metal)   # crossbar
	_wheels.append(_wheel(front, FRONT_AXLE - HEAD_BOT))
	for x: float in [-0.09, 0.09]:
		_tube(front, FRONT_AXLE - HEAD_BOT + Vector3(x, 0, 0), FRONT_AXLE - HEAD_BOT + Vector3(x * 1.9, 0, 0), 0.02, _metal)


func _material(c: Color, rough: float, metal: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = rough
	m.metallic = metal
	return m


func _tube(parent: Node3D, a: Vector3, b: Vector3, r: float, m: Material) -> void:
	var len := a.distance_to(b)
	if len < 0.0005:
		return
	var mi := MeshInstance3D.new()
	var c := CylinderMesh.new()
	c.top_radius = r
	c.bottom_radius = r
	c.height = len
	c.radial_segments = 10
	c.rings = 1
	c.material = m
	mi.mesh = c
	var y := (b - a) / len
	var x := y.cross(Vector3.FORWARD if absf(y.z) < 0.9 else Vector3.RIGHT).normalized()
	mi.transform = Transform3D(Basis(x, y, x.cross(y)), (a + b) * 0.5)
	parent.add_child(mi)


func _box(parent: Node3D, size: Vector3, pos: Vector3, m: Material) -> void:
	var mi := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = size
	b.material = m
	mi.mesh = b
	mi.position = pos
	parent.add_child(mi)


func _wheel(parent: Node3D, at: Vector3) -> Node3D:
	var w := Node3D.new()
	w.position = at
	parent.add_child(w)
	var tire := MeshInstance3D.new()
	var t := TorusMesh.new()
	t.inner_radius = WHEEL_R - 0.045
	t.outer_radius = WHEEL_R
	t.rings = 32
	t.ring_segments = 10
	t.material = _rubber
	tire.mesh = t
	tire.rotation = Vector3(0, 0, PI / 2)     # torus axis along X
	w.add_child(tire)
	var rim := MeshInstance3D.new()
	var rm := TorusMesh.new()
	rm.inner_radius = WHEEL_R - 0.06
	rm.outer_radius = WHEEL_R - 0.04
	rm.rings = 32
	rm.ring_segments = 6
	rm.material = _metal
	rim.mesh = rm
	rim.rotation = Vector3(0, 0, PI / 2)
	w.add_child(rim)
	for k in 12:
		var a := TAU * k / 12.0
		_tube(w, Vector3(0.03 * (1 if k % 2 else -1), 0, 0), Vector3(0, cos(a), sin(a)) * (WHEEL_R - 0.055), 0.003, _metal)
	_tube(w, Vector3(-0.05, 0, 0), Vector3(0.05, 0, 0), 0.025, _metal)   # hub
	return w


## Spin wheels and cranks; pedaling turns the cranks, coasting leaves them still.
func roll(dt: float, speed: float, pedaling: bool) -> void:
	var spin := speed / WHEEL_R * dt
	for w in _wheels:
		w.rotate_x(spin)
	if pedaling:
		crank_angle += spin / 2.3
	crank.rotation = Vector3(crank_angle, 0, 0)
	front.basis = Basis(_axis, bar_angle)
	frame.basis = Basis(_axis, whip_angle)


## Pedal positions in bike space: [left, right].
func pedals() -> Array:
	var out := []
	for side: float in [1.0, -1.0]:
		var local := Vector3(0.13 * side, 0, CRANK * side).rotated(Vector3.RIGHT, crank_angle)
		out.append(frame.transform * (crank.position + local) + Vector3(0, 0.03, 0))
	return out


## Grip positions in bike space: [left, right].
func grips() -> Array:
	var stem := HEAD_TOP - HEAD_BOT + _axis * 0.06
	var mid := stem + Vector3(0, 0.12, -0.03)
	return [front.transform * (mid + Vector3(0.27, 0.02, -0.02)), front.transform * (mid + Vector3(-0.27, 0.02, -0.02))]
