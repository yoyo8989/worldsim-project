# TerrainAscii.gd
# Supports full redraw or diff-based cell updates via apply_ascii_diff
# License: MIT

extends TileMap
class_name TerrainAscii

signal error(message: String)
signal tiles_updated(key: Vector2i)

@export var tile_size: int = 1
@export var batch_size: int = 100
@export var tile_variants: int = 10

# Internal previous state map: (cx,cy) -> flat Array
var previous_tiles: Dictionary = {}

func update_tiles(cx: int, cy: int, tile_array: Array, full_flag: int) -> void:
	var key = Vector2i(cx, cy)
	if full_flag == 1 or not previous_tiles.has(key):
		_full_update(tile_array)
		previous_tiles[key] = tile_array.duplicate()
	else:
		apply_ascii_diff(tile_array)
		previous_tiles[key] = _apply_diff_to_flat(previous_tiles[key], tile_array)
	emit_signal("tiles_updated", key)

func _full_update(arr: Array) -> void:
	clear()
	_draw_ascii(arr)

func _draw_ascii(arr: Array) -> void:
	var total: int = arr.size()
	var dim: int = int(sqrt(total))
	for i in range(total):
		var v: float = float(arr[i])
		var tid: int = clamp(int(v * tile_variants), 0, tile_variants - 1)
		var x: int = i % dim
		var y: int = i / dim
		set_cell(0, Vector2i(x, y), tid)
		if i % batch_size == 0:
			await get_tree().process_frame

func apply_ascii_diff(diffs: Array) -> void:
	# diffs: [{"index":int, "value":Variant}, ...]
	var base = previous_tiles.values()[0]
	var dim = int(sqrt(base.size()))
	for d in diffs:
		var idx = int(d["index"])
		var v: float = float(d["value"])
		var tid: int = clamp(int(v * tile_variants), 0, tile_variants - 1)
		var x: int = idx % dim
		var y: int = idx / dim
		set_cell(0, Vector2i(x, y), tid)

func _apply_diff_to_flat(base: Array, diffs: Array) -> Array:
	var result: Array = base.duplicate()
	for d in diffs:
		result[d["index"]] = d["value"]
	return result

# clear() and set_cell() are inherited from TileMap
