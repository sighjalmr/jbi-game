extends Node
## Input actions are registered in code so the mapping lives in one readable place.

const KEYS := {
	"push": [KEY_W, KEY_UP],
	"brake": [KEY_S, KEY_DOWN],
	"left": [KEY_A, KEY_LEFT],
	"right": [KEY_D, KEY_RIGHT],
	"ollie": [KEY_SPACE],
	"flip": [KEY_J],
	"heelflip": [KEY_K],
	"shove": [KEY_L],
	"grab": [KEY_I],
	"respawn": [KEY_R],
	"next_spot": [KEY_T],
	"toggle_quality": [KEY_F2],
	"toggle_skate": [KEY_F],
	"toggle_bmx": [KEY_B],
}
const PAD_BUTTONS := {
	"ollie": [JOY_BUTTON_A],
	"flip": [JOY_BUTTON_X],
	"heelflip": [JOY_BUTTON_RIGHT_SHOULDER],
	"shove": [JOY_BUTTON_LEFT_SHOULDER],
	"grab": [JOY_BUTTON_Y],
	"brake": [JOY_BUTTON_B],
	"respawn": [JOY_BUTTON_BACK],
	"next_spot": [JOY_BUTTON_DPAD_UP],
	"toggle_skate": [JOY_BUTTON_DPAD_LEFT],
	"toggle_bmx": [JOY_BUTTON_DPAD_RIGHT],
}
const PAD_AXES := {
	"push": [JOY_AXIS_LEFT_Y, -1.0],
	"brake": [JOY_AXIS_LEFT_Y, 1.0],
	"left": [JOY_AXIS_LEFT_X, -1.0],
	"right": [JOY_AXIS_LEFT_X, 1.0],
}


func _ready() -> void:
	for action in KEYS:
		_ensure(action)
		for k in KEYS[action]:
			var e := InputEventKey.new()
			e.physical_keycode = k
			InputMap.action_add_event(action, e)
	for action in PAD_BUTTONS:
		_ensure(action)
		for b in PAD_BUTTONS[action]:
			var e := InputEventJoypadButton.new()
			e.button_index = b
			InputMap.action_add_event(action, e)
	for action in PAD_AXES:
		_ensure(action)
		var e := InputEventJoypadMotion.new()
		e.axis = PAD_AXES[action][0]
		e.axis_value = PAD_AXES[action][1]
		InputMap.action_add_event(action, e)


func _ensure(action: String) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action, 0.25)
