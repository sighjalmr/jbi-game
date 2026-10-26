extends CanvasLayer
## Score, current combo, grind balance and the controls hint.

@export var skater_path: NodePath

var skater: Skater
var score := 0
var _flash := 0.0
var _flash_text := ""

@onready var score_label: Label = $Score
@onready var combo_label: Label = $Combo
@onready var flash_label: Label = $Flash
@onready var balance_bar: ProgressBar = $Balance
@onready var info_label: Label = $Info


func _ready() -> void:
	skater = get_node(skater_path)
	skater.combo_banked.connect(_on_banked)
	skater.bailed.connect(func(): _show("БЭЙЛ!"))


func _on_banked(points: int) -> void:
	score += points
	_show("+%d" % points)


func _show(t: String) -> void:
	_flash_text = t
	_flash = 1.4


func _process(dt: float) -> void:
	score_label.text = "СЧЁТ  %d" % score
	if skater.combo_tricks.size() > 0 and skater.state != Skater.State.GROUND:
		combo_label.text = "%s\n%d x %d" % [" + ".join(skater.combo_tricks.slice(-4)), skater.combo_points, skater.combo_multiplier()]
	else:
		combo_label.text = ""
	balance_bar.visible = skater.state == Skater.State.GRIND
	balance_bar.value = skater.balance
	_flash = maxf(0.0, _flash - dt)
	flash_label.text = _flash_text if _flash > 0.0 else ""
	info_label.text = "%s  %d км/ч" % [skater.mode_name(), int(absf(skater.speed) * 3.6)]
