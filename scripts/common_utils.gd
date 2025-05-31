# res://scripts/common_utils.gd
# Shared utility functions for TerrainLoader and TerrainAscii modules
# License: MIT

@tool
extends Node
class_name CommonUtils

# Byte conversion helpers using PackedByteArray
static func int32_to_bytes(i: int) -> PackedByteArray:
	var b = PackedByteArray()
	b.resize(4)
	b[0] = (i >> 24) & 0xFF
	b[1] = (i >> 16) & 0xFF
	b[2] = (i >> 8) & 0xFF
	b[3] = i & 0xFF
	return b

static func bytes_to_int32(buf: PackedByteArray) -> int:
	if buf.size() < 4:
		push_error("bytes_to_int32: buffer too small (size=%d)" % buf.size())
		return 0
	return (buf[0] << 24) | (buf[1] << 16) | (buf[2] << 8) | buf[3]

# Request header builder: full_flag(1) + cx(4) + cy(4) + lod(1)
static func build_request_header(full_flag: int, cx: int, cy: int, lod: float) -> PackedByteArray:
	var header = PackedByteArray()
	header.resize(10)
	header[0] = clamp(full_flag, 0, 1)
	# cx
	header[1] = (cx >> 24) & 0xFF
	header[2] = (cx >> 16) & 0xFF
	header[3] = (cx >> 8) & 0xFF
	header[4] = cx & 0xFF
	# cy
	header[5] = (cy >> 24) & 0xFF
	header[6] = (cy >> 16) & 0xFF
	header[7] = (cy >> 8) & 0xFF
	header[8] = cy & 0xFF
	# lod
	header[9] = int(clamp(lod, 0.0, 1.0) * 255)
	return header

# Safe signal emitter with varargs expansion
static func safe_emit(node: Object, signal_name: String, args: Array) -> void:
	if node and node.has_signal(signal_name):
		# callv を使って配列を展開しシグナルを発行
		node.callv("emit_signal", [signal_name] + args)
	else:
		push_warning("SafeEmit: Signal '%s' not found on %s" % [signal_name, str(node)])
