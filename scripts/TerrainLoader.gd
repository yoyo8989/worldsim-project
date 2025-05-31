# TerrainLoader.gd
# Optimized TCP client with full/diff requests and diff-based updates
# Author: Adapted for Godot 4
# License: MIT

extends Node
class_name TerrainLoader

signal terrain_ready(flat_array: PackedFloat32Array, dim: int)
signal terrain_error(message: String)

@export var host: String = "127.0.0.1"
@export var port: int = 6000
@export var request_header_size: int = 10  # 1 flag + 4cx + 4cy + 1 lod

const MSGPACK = preload("res://addons/msgpack/msgpack.gd")

var _peer: StreamPeerTCP
var previous_tiles: Dictionary = {}  # key: Vector2i(cx,cy), value: Array
# store last requested coordinates for mapping responses
var _last_request_cx: int = 0
var _last_request_cy: int = 0

func _ready() -> void:
	_peer = StreamPeerTCP.new()
	call_deferred("_connect_and_listen")

func request_chunk(cx: int, cy: int, lod: float, full_flag: int = 1) -> void:
	# remember coords before sending
	_last_request_cx = cx
	_last_request_cy = cy
	var ba: PackedByteArray = PackedByteArray()
	ba.append(full_flag)
	ba.append_array(_int32_to_bytes(cx))
	ba.append_array(_int32_to_bytes(cy))
	ba.append(int(clamp(lod, 0.0, 1.0) * 255))
	_peer.put_data(ba)

func _connect_and_listen() -> void:
	if _peer.connect_to_host(host, port) != OK:
		emit_signal("terrain_error", "Connection failed")
		return
	await get_tree().process_frame
	_listen_loop()

func _listen_loop() -> void:
	while true:
		# read length prefix
		var hdr: PackedByteArray = _peer.get_data(4)
		if hdr.size() < 4:
			emit_signal("terrain_error", "Header read failed")
			return
		var length: int = _bytes_to_int32(hdr)
		# read payload
		var payload: PackedByteArray = _peer.get_data(length)
		if payload.size() != length:
			emit_signal("terrain_error", "Incomplete payload")
			return
		# parse full_flag and content
		var full_flag: int = payload[0]
		# extract content without the first byte
		var content: PackedByteArray = PackedByteArray()
		var content_size := length - 1
		content.resize(content_size)
		for i in range(content_size):
			content[i] = payload[i + 1]
		# use stored request coords
		var key: Vector2i = Vector2i(_last_request_cx, _last_request_cy)
		var new_tiles: Array
		if full_flag == 0 and previous_tiles.has(key):
			var dres = MSGPACK.decode_diff(previous_tiles[key], content)
			if dres.error != OK:
				emit_signal("terrain_error", "Diff decode error %d" % dres.error)
				return
			new_tiles = dres.result
		else:
			var dres = MSGPACK.decode(content)
			if dres.error != OK:
				emit_signal("terrain_error", "Decode error %d" % dres.error)
				return
			new_tiles = dres.result
		previous_tiles[key] = new_tiles
		_apply_tiles(new_tiles)

func _apply_tiles(arr: Array) -> void:
	var total: int = arr.size()
	var dim: int = int(sqrt(total))
	emit_signal("terrain_ready", TerrainLoader.PackFloat32Array(arr), dim)

# Helpers
func _int32_to_bytes(i: int) -> PackedByteArray:
	var b: PackedByteArray = PackedByteArray()
	b.resize(4)
	b[0] = (i >> 24) & 0xFF
	b[1] = (i >> 16) & 0xFF
	b[2] = (i >> 8) & 0xFF
	b[3] = i & 0xFF
	return b

func _bytes_to_int32(b: PackedByteArray) -> int:
	return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]

static func PackFloat32Array(arr: Array) -> PackedFloat32Array:
	var buf: PackedFloat32Array = PackedFloat32Array()
	buf.resize(arr.size())
	for j in range(arr.size()):
		buf[j] = float(arr[j])
	return buf
