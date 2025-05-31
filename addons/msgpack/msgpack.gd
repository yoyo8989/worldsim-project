# msgpack.gd
# Msgpack wrapper with queued threading for serialization/deserialization
# and diff format support (compute/apply diffs)
# License: MIT

extends Node
class_name Msgpack

signal encode_completed(result: Dictionary)
signal decode_completed(result: Dictionary)
signal error(message: String)

@export var max_queue_size: int = 10  # max pending tasks to avoid memory bloat
var _encode_thread: Thread = Thread.new()
var _decode_thread: Thread = Thread.new()
var _encode_queue: Array = []  # pending encode variants
var _decode_queue: Array = []  # pending decode buffers

static func encode(value) -> Dictionary:
	if value == null:
		return {"result": null, "error": ERR_INVALID_DATA, "error_string": "Cannot encode null"}
	var packed: PackedByteArray = var_to_bytes(value)
	if packed.size() == 0:
		return {"result": null, "error": ERR_CANT_CREATE, "error_string": "Empty buffer after serialization"}
	return {"result": packed, "error": OK, "error_string": ""}

static func decode(bytes: PackedByteArray) -> Dictionary:
	if bytes.size() == 0:
		return {"result": null, "error": ERR_PARSE_ERROR, "error_string": "Empty buffer"}
	var value: Variant = bytes_to_var(bytes)
	return {"result": value, "error": OK, "error_string": ""}

# Diff computation between two Variants (Dictionary or Array or primitive)
static func compute_diff(old, new) -> Variant:
	if typeof(old) == TYPE_DICTIONARY and typeof(new) == TYPE_DICTIONARY:
		var diff: Dictionary = {}
		for key in new.keys():
			if not old.has(key) or old[key] != new[key]:
				diff[key] = new[key]
		for key in old.keys():
			if not new.has(key):
				diff[key] = null
		return diff
	elif typeof(old) == TYPE_ARRAY and typeof(new) == TYPE_ARRAY:
		var diffs: Array = []
		var min_len = min(old.size(), new.size())
		for i in range(min_len):
			if old[i] != new[i]:
				diffs.append({"index": i, "value": new[i]})
		for i in range(min_len, new.size()):
			diffs.append({"index": i, "value": new[i]})
		return diffs
	else:
		return new if old != new else null

# Apply a diff to a base Variant
static func apply_diff(base, diff) -> Variant:
	if diff == null:
		return base
	if typeof(base) == TYPE_DICTIONARY and typeof(diff) == TYPE_DICTIONARY:
		var result: Dictionary = base.duplicate()
		for key in diff.keys():
			if diff[key] == null:
				result.erase(key)
			else:
				result[key] = diff[key]
		return result
	elif typeof(base) == TYPE_ARRAY and typeof(diff) == TYPE_ARRAY:
		var result: Array = []
		for i in range(base.size()):
			result.append(base[i])
		for item in diff:
			result[item["index"]] = item["value"]
		return result
	else:
		return diff

# Diff encode/decode wrappers
static func encode_diff(old, new) -> Dictionary:
	var d = compute_diff(old, new)
	return encode(d)

static func decode_diff(base, bytes: PackedByteArray) -> Dictionary:
	var dres = decode(bytes)
	if dres.error != OK:
		return dres
	var updated = apply_diff(base, dres.result)
	return {"result": updated, "error": OK, "error_string": ""}

# Threaded async encode/decode (unchanged)
func encode_async(value) -> void:
	if _encode_queue.size() >= max_queue_size:
		_encode_queue.pop_front()
	_encode_queue.append(value)
	if not _encode_thread.is_active():
		_process_next_encode()

func _process_next_encode() -> void:
	if _encode_queue.is_empty():
		return
	var data = _encode_queue.front()
	var err = _encode_thread.start(Callable(self, "_thread_encode"), data)
	if err != OK:
		_encode_queue.pop_front()
		emit_signal("error", "Failed to start encode thread: %d" % err)

func _thread_encode(data) -> void:
	var result = Msgpack.encode(data)
	call_deferred("_emit_encode_completed", result)

func _emit_encode_completed(result: Dictionary) -> void:
	emit_signal("encode_completed", result)
	_encode_thread.wait_to_finish()
	_encode_queue.pop_front()
	_process_next_encode()

func decode_async(bytes: PackedByteArray) -> void:
	if _decode_queue.size() >= max_queue_size:
		_decode_queue.pop_front()
	_decode_queue.append(bytes)
	if not _decode_thread.is_active():
		_process_next_decode()

func _process_next_decode() -> void:
	if _decode_queue.is_empty():
		return
	var data = _decode_queue.front()
	var err = _decode_thread.start(Callable(self, "_thread_decode"), data)
	if err != OK:
		_decode_queue.pop_front()
		emit_signal("error", "Failed to start decode thread: %d" % err)

func _thread_decode(data) -> void:
	var result = Msgpack.decode(data)
	call_deferred("_emit_decode_completed", result)

func _emit_decode_completed(result: Dictionary) -> void:
	emit_signal("decode_completed", result)
	_decode_thread.wait_to_finish()
	_decode_queue.pop_front()
	_process_next_decode()

static func find_boundary(buffer: PackedByteArray) -> int:
	if buffer.size() < 4:
		return -1
	var length = (buffer[0] << 24) | (buffer[1] << 16) | (buffer[2] << 8) | buffer[3]
	if buffer.size() >= 4 + length:
		return 4 + length
	return -1
