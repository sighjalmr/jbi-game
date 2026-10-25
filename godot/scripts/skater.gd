extends CharacterBody3D
class_name Skater
## Tony Hawk style skateboard: push, carve, ollie, flip tricks, spins and rail grinds.
## The origin is at the skater's feet; the model faces +Z.

signal trick_done(name: String, points: int)
signal combo_banked(points: int)
signal bailed

enum State { GROUND, AIR, GRIND, BAIL }

@export var world_path: NodePath
@export var push_accel := 6.0
@export var push_max := 9.5
@export var top_speed := 22.0
@export var brake_decel := 9.0
@export var rolling_friction := 0.35
@export var turn_rate := 2.6
@export var ollie_speed := 7.2
@export var gravity := 19.0
@export var air_spin_rate := 6.5
@export var grind_catch := 0.75

var state := State.GROUND
var yaw := 0.0
var speed := 0.0
var world: WorldBuilder

# trick and combo bookkeeping
var combo_points := 0
var combo_tricks: Array[String] = []
var flip_time := 0.0
var flip_axis := Vector3.ZERO
var spin_accum := 0.0
var grab_time := 0.0
var air_time := 0.0
var bail_time := 0.0
var last_trick := ""

# grind state
var rail := -1
var rail_s := 0.0        # distance along the rail polyline
var rail_dir := 1.0
var balance := 0.0
var balance_drift := 0.0
var grind_time := 0.0
var grind_cooldown := 0.0

# presses are buffered briefly so a tap between physics ticks is never lost
var _buffer := {}

var visual: Node3D
var board: Node3D
var body: Node3D

const FLIP_DURATION := 0.42
const TRICKS := {
	"flip": ["Kickflip", 100, Vector3(0, 0, 1)],
	"heelflip": ["Heelflip", 100, Vector3(0, 0, -1)],
	"shove": ["Shove-it", 80, Vector3(0, 1, 0)],
}


func _ready() -> void:
	world = get_node(world_path)
	floor_snap_length = 0.7
	floor_max_angle = deg_to_rad(52.0)
	floor_stop_on_slope = false
	floor_constant_speed = true
	_build_model()
	respawn(0)


# ---------------------------------------------------------------- public

func respawn(i: int) -> void:
	var sp: Dictionary = world.spawn_points[i % world.spawn_points.size()]
	global_position = sp.p
	yaw = sp.yaw
	speed = 0.0
	velocity = Vector3.ZERO
	state = State.AIR
	_reset_combo()
	_reset_pose()


func forward() -> Vector3:
	return Vector3(sin(yaw), 0, cos(yaw))


func grind_name() -> String:
	return world.rails[rail].name if state == State.GRIND else ""


func combo_multiplier() -> int:
	return maxi(1, combo_tricks.size())


# ---------------------------------------------------------------- physics

func _input(e: InputEvent) -> void:
	for action in ["ollie", "flip", "heelflip", "shove"]:
		if e.is_action_pressed(action):
			_buffer[action] = 0.15


func _pressed(action: String) -> bool:
	if _buffer.get(action, 0.0) > 0.0:
		_buffer[action] = 0.0
		return true
	return false


func _physics_process(dt: float) -> void:
	grind_cooldown = maxf(0.0, grind_cooldown - dt)
	for action in _buffer:
		_buffer[action] = maxf(0.0, _buffer[action] - dt)
	match state:
		State.GROUND: _ground(dt)
		State.AIR: _air(dt)
		State.GRIND: _grind(dt)
		State.BAIL: _bailing(dt)
	_update_visual(dt)


func _steer() -> float:
	return Input.get_action_strength("left") - Input.get_action_strength("right")


func _ground(dt: float) -> void:
	var n := get_floor_normal() if is_on_floor() else Vector3.UP
	var fwd := (forward() - n * forward().dot(n)).normalized()
	# gravity along the slope, pushing, braking, friction
	speed += -gravity * fwd.y * dt
	if Input.is_action_pressed("push") and speed < push_max:
		speed = minf(push_max, speed + push_accel * dt)
	if Input.is_action_pressed("brake"):
		speed = move_toward(speed, 0.0, brake_decel * dt)
	speed = move_toward(speed, 0.0, rolling_friction * dt)
	speed = clampf(speed, -6.0, top_speed)
	var steer := _steer()
	yaw += steer * turn_rate * dt * (1.0 if speed >= 0.0 else -1.0) * clampf(1.15 - absf(speed) / 40.0, 0.6, 1.0)

	velocity = fwd * speed
	if _pressed("ollie"):
		velocity += n * ollie_speed
		_take_off("Ollie", 10)
		move_and_slide()
		return
	move_and_slide()
	if _hit_wall():
		return
	# carry over what the physics actually allowed (walls, kerbs)
	speed = signf(speed) * minf(absf(speed), get_real_velocity().length())
	if not is_on_floor():
		state = State.AIR
		air_time = 0.0
		spin_accum = 0.0


func _take_off(name: String, points: int) -> void:
	state = State.AIR
	air_time = 0.0
	spin_accum = 0.0
	_add_trick(name, points)


func _hit_wall() -> bool:
	for i in get_slide_collision_count():
		var c := get_slide_collision(i)
		var n := c.get_normal()
		if absf(n.y) < 0.4 and n.dot(forward()) < -0.75 and absf(speed) > 7.0:
			_bail()
			return true
	return false


func _air(dt: float) -> void:
	air_time += dt
	velocity.y -= gravity * dt
	var spin := _steer() * air_spin_rate * dt
	yaw += spin
	spin_accum += spin

	for action in TRICKS:
		if flip_time <= 0.0 and _pressed(action):
			flip_time = FLIP_DURATION
			flip_axis = TRICKS[action][2]
			_add_trick(TRICKS[action][0], TRICKS[action][1])
	if flip_time > 0.0:
		flip_time = maxf(0.0, flip_time - dt)
	if Input.is_action_pressed("grab") and flip_time <= 0.0:
		grab_time += dt
	elif grab_time > 0.0:
		if grab_time > 0.25:
			_add_trick("Indy Grab", int(60 + grab_time * 120))
		grab_time = 0.0

	if velocity.y < 0.0 and grind_cooldown <= 0.0 and _try_grind():
		return
	move_and_slide()
	if is_on_floor() and velocity.y <= 0.1:
		_land()


func _land() -> void:
	var hv := Vector3(velocity.x, 0, velocity.z)
	_score_spin()
	if flip_time > 0.0 or grab_time > 0.15:
		_bail()
		return
	if hv.length() > 1.0:
		var diff := absf(wrapf(atan2(hv.x, hv.z) - yaw, -PI, PI))
		if diff > deg_to_rad(65.0) and diff < deg_to_rad(115.0):
			_bail()
			return
		if diff >= deg_to_rad(115.0):
			yaw += PI      # rolled out backwards: keep going, now facing the motion
	state = State.GROUND
	speed = hv.length()
	_bank_combo()


func _score_spin() -> void:
	var turns := int(roundf(absf(spin_accum) / PI))
	if turns >= 1:
		_add_trick("%d" % (turns * 180), turns * 90)
	spin_accum = 0.0


# ---------------------------------------------------------------- grinding

func _try_grind() -> bool:
	var feet := global_position
	var best := -1
	var best_seg := 0
	var best_d := grind_catch
	var best_t := 0.0
	var next := feet + velocity * get_physics_process_delta_time()
	for rs in world.rails_near(feet):
		var pts: PackedVector3Array = world.rails[rs.x].pts
		var a := pts[rs.y]
		var b := pts[rs.y + 1]
		var ab := b - a
		var t := clampf((feet - a).dot(ab) / ab.length_squared(), 0.0, 1.0)
		var c := a + ab * t
		var dh := Vector2(feet.x - c.x, feet.z - c.z).length()
		var dy := feet.y - c.y
		# coming down onto the rail from above (or just through it this frame)
		if dh < best_d and dy > -0.35 and (dy < 0.45 or next.y - c.y < 0.1):
			best = rs.x; best_seg = rs.y; best_d = dh; best_t = t
	if best < 0:
		return false
	var pts: PackedVector3Array = world.rails[best].pts
	var s := 0.0
	for i in best_seg:
		s += pts[i].distance_to(pts[i + 1])
	s += pts[best_seg].distance_to(pts[best_seg + 1]) * best_t
	var dir := (pts[best_seg + 1] - pts[best_seg]).normalized()
	var along := velocity.dot(dir)
	rail = best
	rail_s = s
	rail_dir = 1.0 if along >= 0.0 else -1.0
	speed = maxf(absf(along), 4.0)
	balance = 0.0
	balance_drift = randf_range(-0.6, 0.6)
	grind_time = 0.0
	_score_spin()
	if flip_time > 0.0:
		_bail()
		return true
	state = State.GRIND
	_add_trick(world.rails[rail].name, 50)
	return true


func _rail_point(pts: PackedVector3Array, s: float) -> Array:
	var acc := 0.0
	for i in pts.size() - 1:
		var l := pts[i].distance_to(pts[i + 1])
		if s <= acc + l or i == pts.size() - 2:
			var t := clampf((s - acc) / maxf(l, 0.001), 0.0, 1.0)
			return [pts[i].lerp(pts[i + 1], t), (pts[i + 1] - pts[i]).normalized()]
		acc += l
	return [pts[0], Vector3.FORWARD]


func _rail_length(pts: PackedVector3Array) -> float:
	var l := 0.0
	for i in pts.size() - 1:
		l += pts[i].distance_to(pts[i + 1])
	return l


func _grind(dt: float) -> void:
	var pts: PackedVector3Array = world.rails[rail].pts
	var here := _rail_point(pts, rail_s)
	var dir: Vector3 = here[1] * rail_dir
	speed += -gravity * dir.y * dt * 0.8
	speed = maxf(speed - 0.4 * dt, 0.5)
	rail_s += rail_dir * speed * dt
	grind_time += dt
	combo_points += int(dt * 40.0)

	# balance: tips over more the further it leans; steer against it
	balance_drift += randf_range(-1.0, 1.0) * dt * 2.0
	balance += (balance * 1.6 + balance_drift) * dt - _steer() * dt * 2.2
	if absf(balance) > 1.0:
		_bail()
		return

	var length := _rail_length(pts)
	var p: Array = _rail_point(pts, clampf(rail_s, 0.0, length))
	global_position = p[0]
	var d: Vector3 = p[1] * rail_dir
	yaw = atan2(d.x, d.z)
	velocity = d * speed

	if _pressed("ollie"):
		velocity += Vector3.UP * ollie_speed * 0.9
		grind_cooldown = 0.3
		_take_off("Ollie", 10)
		return
	if rail_s < 0.0 or rail_s > length:
		grind_cooldown = 0.25
		state = State.AIR
		air_time = 0.0


# ---------------------------------------------------------------- bails and scoring

func _bail() -> void:
	state = State.BAIL
	bail_time = 1.3
	flip_time = 0.0
	grab_time = 0.0
	combo_points = 0
	combo_tricks.clear()
	bailed.emit()


func _bailing(dt: float) -> void:
	bail_time -= dt
	velocity.x *= 1.0 - minf(1.0, 2.5 * dt)
	velocity.z *= 1.0 - minf(1.0, 2.5 * dt)
	velocity.y -= gravity * dt
	move_and_slide()
	if bail_time <= 0.0:
		speed = 0.0
		velocity = Vector3.ZERO
		state = State.GROUND if is_on_floor() else State.AIR
		_reset_pose()


func _add_trick(name: String, points: int) -> void:
	combo_tricks.append(name)
	combo_points += points
	last_trick = name
	trick_done.emit(name, points)


func _bank_combo() -> void:
	if combo_tricks.size() > 1 or (combo_tricks.size() == 1 and combo_tricks[0] != "Ollie"):
		combo_banked.emit(combo_points * combo_multiplier())
	_reset_combo()


func _reset_combo() -> void:
	combo_points = 0
	combo_tricks.clear()
	spin_accum = 0.0


# ---------------------------------------------------------------- model

func _box(parent: Node3D, size: Vector3, pos: Vector3, col: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var m := BoxMesh.new()
	m.size = size
	var mat := StandardMaterial3D.new()
	mat.albedo_color = col
	mat.roughness = 0.8
	m.material = mat
	mi.mesh = m
	mi.position = pos
	parent.add_child(mi)
	return mi


func _capsule(parent: Node3D, radius: float, height: float, pos: Vector3, col: Color, rot := Vector3.ZERO) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var m := CapsuleMesh.new()
	m.radius = radius
	m.height = height
	m.radial_segments = 12
	m.rings = 4
	var mat := StandardMaterial3D.new()
	mat.albedo_color = col
	mat.roughness = 0.85
	m.material = mat
	mi.mesh = m
	mi.position = pos
	mi.rotation = rot
	parent.add_child(mi)
	return mi


func _build_model() -> void:
	visual = Node3D.new()
	visual.name = "Visual"
	add_child(visual)
	board = Node3D.new()
	board.name = "Board"
	board.position = Vector3(0, 0.1, 0)
	visual.add_child(board)
	_box(board, Vector3(0.22, 0.035, 0.82), Vector3.ZERO, Color(0.85, 0.2, 0.12))
	_box(board, Vector3(0.21, 0.01, 0.8), Vector3(0, 0.022, 0), Color(0.12, 0.12, 0.12))   # grip tape
	for z: float in [-0.28, 0.28]:
		_box(board, Vector3(0.16, 0.04, 0.05), Vector3(0, -0.04, z), Color(0.7, 0.7, 0.72))
		for x: float in [-0.1, 0.1]:
			_box(board, Vector3(0.05, 0.06, 0.06), Vector3(x, -0.07, z), Color(0.95, 0.92, 0.8))

	# rider stands sideways on the deck, chest towards +X
	body = Node3D.new()
	body.name = "Body"
	body.position = Vector3(0, 0.14, 0)
	visual.add_child(body)
	var jeans := Color(0.22, 0.28, 0.45)
	var hoodie := Color(0.2, 0.42, 0.3)
	var skin := Color(0.92, 0.74, 0.6)
	for z: float in [-0.17, 0.17]:
		_capsule(body, 0.085, 0.84, Vector3(0, 0.46, z), jeans, Vector3(z * 0.25, 0, 0))
		_box(body, Vector3(0.28, 0.08, 0.12), Vector3(0.04, 0.04, z * 1.08), Color(0.92, 0.92, 0.9))   # sneakers
	_capsule(body, 0.2, 0.66, Vector3(0, 1.12, 0), hoodie).scale = Vector3(0.8, 1.0, 1.15)
	for z: float in [-0.27, 0.27]:
		_capsule(body, 0.065, 0.6, Vector3(0, 1.07, z), hoodie, Vector3(-signf(z) * 0.25, 0, 0))
		_capsule(body, 0.05, 0.12, Vector3(0, 0.76, z * 1.12), skin)
	_capsule(body, 0.05, 0.14, Vector3(0, 1.47, 0), skin)
	var head := MeshInstance3D.new()
	var hm := SphereMesh.new()
	hm.radius = 0.12
	hm.height = 0.27
	var hmat := StandardMaterial3D.new()
	hmat.albedo_color = skin
	hm.material = hmat
	head.mesh = hm
	head.position = Vector3(0.01, 1.6, 0)
	body.add_child(head)
	_capsule(body, 0.125, 0.26, Vector3(-0.01, 1.68, 0), Color(0.12, 0.12, 0.14)).scale = Vector3(1, 0.55, 1)   # beanie



func _reset_pose() -> void:
	if not visual:
		return
	board.transform = Transform3D(Basis(), Vector3(0, 0.1, 0))
	body.transform = Transform3D(Basis(), Vector3(0, 0.14, 0))


func _update_visual(dt: float) -> void:
	var up := Vector3.UP
	if state == State.GROUND and is_on_floor():
		up = get_floor_normal()
	var f := forward()
	var right := up.cross(f).normalized()
	var target := Basis(right, up, right.cross(up)).orthonormalized()
	visual.basis = visual.basis.slerp(target, minf(1.0, dt * 12.0)).orthonormalized()

	_reset_pose()
	match state:
		State.AIR:
			body.scale = Vector3(1, 0.88, 1)
			if flip_time > 0.0:
				var k := 1.0 - flip_time / FLIP_DURATION
				board.basis = Basis(flip_axis, k * TAU)
				board.position.y = 0.1 + sin(k * PI) * 0.25
			elif grab_time > 0.0:
				body.scale = Vector3(1, 0.7, 1)
				board.position.y = 0.3
		State.GRIND:
			body.basis = Basis(Vector3(0, 0, 1), balance * 0.6)
			body.scale = Vector3(1, 0.9, 1)
		State.BAIL:
			var k := 1.0 - bail_time / 1.3
			body.basis = Basis(Vector3(0, 0, 1), -minf(k * 3.0, 1.0) * PI * 0.5)
			body.position = Vector3(0.0, 0.15, 0)
			board.position = Vector3(0.0, 0.05, 0.6 + k * 1.5)
			board.basis = Basis(Vector3(1, 0, 0), k * 5.0)
		_:
			body.scale = Vector3.ONE
			if Input.is_action_pressed("push") and speed < push_max:
				body.basis = Basis(Vector3(0, 0, 1), sin(Time.get_ticks_msec() * 0.012) * 0.12)
