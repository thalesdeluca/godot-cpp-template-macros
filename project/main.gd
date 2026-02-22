extends Node3D


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	$Example.calculate_test(0, 1, 2)
	pass # Replace with function body.


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	pass


func _on_example_test_signal(param1: float, param2: int) -> void:
	print("test")
	pass # Replace with function body.
