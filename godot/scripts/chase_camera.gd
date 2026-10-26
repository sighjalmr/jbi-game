extends Camera3D
## Third person camera that trails the skater like in the old Tony Hawk games.

@export var target_path: NodePath
@export var distance := 4.6
@export var height := 1.9
@export var look_height := 1.1
@export var follow := 5.0

var skater: Skater
var _yaw := 0.0


func _ready() -> void:
	skater = get_node(target_path)
	top_level = true
	_yaw = skater.yaw
	snap()


func snap() -> void:
	_yaw = skater.yaw
	global_position = _desired()
	look_at(skater.global_position + Vector3.UP * look_height)


func _desired() -> Vector3:
	var back := -Vector3(sin(_yaw), 0, cos(_yaw))
	var focus := skater.global_position + Vector3.UP * look_height
	var want := skater.global_position + back * distance + Vector3.UP * height
	# keep the camera out of walls
	var q := PhysicsRayQueryParameters3D.create(focus, want)
	q.exclude = [skater.get_rid()]
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	if hit:
		want = hit.position + (focus - want).normalized() * 0.3
	return want


func _physics_process(dt: float) -> void:
	# in the air follow the direction of travel, so spins don't swing the camera around
	var aim := skater.yaw
	var hv := Vector3(skater.velocity.x, 0, skater.velocity.z)
	if skater.state != Skater.State.GROUND and hv.length() > 1.0:
		aim = atan2(hv.x, hv.z)
	_yaw = lerp_angle(_yaw, aim, minf(1.0, dt * 3.0))
	global_position = global_position.lerp(_desired(), minf(1.0, dt * follow))
	look_at(skater.global_position + Vector3.UP * look_height)
