extends Node3D
## Level glue: respawn, spot switching, quality toggle and the screenshot tour.

@onready var world: WorldBuilder = $World
@onready var skater: Skater = $Skater
@onready var cam: Camera3D = $Camera
@onready var hud = $HUD

var spot := 0


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	for a in args:
		if a.begins_with("--shots="):
			_shot_tour(a.trim_prefix("--shots="))


func _unhandled_input(e: InputEvent) -> void:
	if e.is_action_pressed("respawn"):
		skater.respawn(spot)
		cam.snap()
	elif e.is_action_pressed("next_spot"):
		spot = (spot + 1) % world.spawn_points.size()
		skater.respawn(spot)
		cam.snap()
		hud._show(world.spawn_points[spot].name)
	elif e.is_action_pressed("toggle_quality"):
		# render 3D at 60% resolution on slower PCs
		var vp := get_viewport()
		var fast := vp.scaling_3d_scale < 1.0
		vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR2 if not fast else Viewport.SCALING_3D_MODE_BILINEAR
		vp.scaling_3d_scale = 1.0 if fast else 0.6
		hud._show("Полное разрешение" if fast else "Быстрый режим")


# ---------------------------------------------------------------- screenshots (godot -- --shots=DIR)

func _frames(n: int) -> void:
	for i in n:
		await get_tree().physics_frame
	await get_tree().process_frame
	await RenderingServer.frame_post_draw


func _save(dir: String, name: String) -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(dir.path_join(name + ".png"))
	print("shot ", name)


func _tap(action: String) -> void:
	var e := InputEventAction.new()
	e.action = action
	e.pressed = true
	Input.parse_input_event(e)


func _ride(frames: int) -> void:
	Input.action_press("push")
	await _frames(frames)
	Input.action_release("push")


## Puts the player on the longest straight bit of road, facing along it.
func _place_on_road(skate_mode: Skater.Mode) -> void:
	var best_seg := []
	var best_l := 0.0
	for r in world.data.roads:
		if r.k != "road":
			continue
		for i in r.p.size() - 1:
			var a := Vector2(r.p[i][0], r.p[i][1])
			var b := Vector2(r.p[i + 1][0], r.p[i + 1][1])
			if a.distance_to(b) > best_l:
				best_l = a.distance_to(b)
				best_seg = [a, b]
	skater.respawn(0)
	skater.set_mode(skate_mode)
	var d: Vector2 = (best_seg[1] - best_seg[0]).normalized()
	skater.global_position = world.ground(best_seg[0].lerp(best_seg[1], 0.3), 0.2)
	skater.yaw = atan2(d.x, d.y)
	cam.snap()


func _shot_tour(dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	var only := OS.get_environment("SHOTS_ONLY")
	cam.distance = 3.6
	cam.height = 1.5
	await _frames(20)
	cam.snap()
	await _frames(5)
	await _save(dir, "01_spawn")

	await _ride(150)
	await _frames(30)
	await _save(dir, "02_stairs_ride")

	# grind: drop onto the longest handrail
	var best := -1
	var best_len := 0.0
	for i in world.rails.size():
		var r: Dictionary = world.rails[i]
		if r.name == "Handrail Grind" and r.pts.size() > best_len:
			best = i
			best_len = r.pts.size()
	if best >= 0:
		var pts: PackedVector3Array = world.rails[best].pts
		var dir3 := (pts[3] - pts[2]).normalized()
		skater.respawn(0)
		skater.global_position = pts[2] + Vector3.UP * 0.25
		skater.velocity = dir3 * 6.0 + Vector3.DOWN * 0.5
		skater.yaw = atan2(dir3.x, dir3.z)
		cam.snap()
		await _frames(25)
		cam.snap()
		await _frames(8)
		await _save(dir, "03_handrail_grind")

	# kickflip on the main road
	_place_on_road(Skater.Mode.SKATE)
	await _frames(10)
	skater.speed = 10.0
	await _ride(60)
	_tap("ollie")
	await _frames(8)
	_tap("flip")
	await _frames(10)
	await _save(dir, "04_kickflip")

	# on foot
	_place_on_road(Skater.Mode.FOOT)
	await _frames(10)
	await _ride(45)
	Input.action_press("push")
	await _frames(1)
	await _save(dir, "05_walk")
	Input.action_release("push")

	# BMX: pedalling, then a tailwhip
	_place_on_road(Skater.Mode.BMX)
	await _frames(10)
	await _ride(70)
	Input.action_press("push")
	await _frames(1)
	await _save(dir, "06_bmx")
	Input.action_release("push")
	_tap("ollie")
	await _frames(10)
	_tap("heelflip")
	await _frames(12)
	await _save(dir, "07_bmx_tailwhip")

	# courtyard of the flats
	set_physics_process(false)
	cam.set_physics_process(false)
	var flats := Vector2(INF, INF)
	for b in world.data.buildings:
		var c := Vector2(b.outer[0][0], b.outer[0][1])
		if b.k == "panel" and c.length() < flats.length():
			flats = c
	var f3 := world.ground(flats)
	cam.global_position = world.ground(flats * 0.8 + Vector2(-30, 0), 2.5)
	cam.look_at(f3 + Vector3(0, 10, 0))
	await _frames(3)
	await _save(dir, "08_yard")
	get_tree().quit()
