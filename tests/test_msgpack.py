import pytest
import msgpack as pymsgpack
import zlib
from server import compute_diff, pack_and_compress, find_boundary

# --- Dict diff tests ---
@pytest.mark.parametrize("old,new,expected_diff", [
    ({'a':1}, {'a':1}, {}),
    ({'a':1}, {'a':2}, {'a':2}),
    ({'a':1}, {}, {'a': None}),
])
def test_compute_diff_dict(old, new, expected_diff):
    diff = compute_diff(old, new)
    assert diff == expected_diff

@pytest.mark.parametrize("old,diff,expected", [
    ({'a':1,'b':2}, {'b':3}, {'a':1,'b':3}),
    ({'a':1}, {'a':None}, {}),
])
def test_apply_diff_dict(old, diff, expected):
    from server_async_chunks_updated_diff import apply_diff
    result = apply_diff(old, diff)
    assert result == expected

# --- List diff tests ---
@pytest.mark.parametrize("old,new,expected_diff", [
    ([1,2,3], [1,2,3], []),
    ([1,2,3], [1,4], [{'index':1,'value':4},{'index':2,'value':None}]),
])
def test_compute_diff_list(old, new, expected_diff):
    diff = compute_diff(old, new)
    assert diff == expected_diff

@pytest.mark.parametrize("old,diff,expected", [
    ([1,2,3], [{'index':1,'value':5}], [1,5,3]),
])
def test_apply_diff_list(old, diff, expected):
    from server_async_chunks_updated_diff import apply_diff
    result = apply_diff(old, diff)
    assert result == expected

# --- pack_and_compress roundtrip ---
def test_pack_and_compress_roundtrip():
    data = [10,20,30]
    payload = pack_and_compress(data)
    length = int.from_bytes(payload[:4], 'big')
    assert length == len(payload) - 4
    comp = payload[4:]
    plain = zlib.decompress(comp)
    unpacked = pymsgpack.unpackb(plain, raw=False)
    assert unpacked == data

# --- find_boundary tests ---
def test_find_boundary_valid():
    # two messages: "hi" and "test"
    msg1 = b"hi"
    msg2 = b"test"
    buf = len(msg1).to_bytes(4,'big') + msg1 + len(msg2).to_bytes(4,'big') + msg2
    paws = find_boundary(bytearray(buf))
    assert paws == 4 + len(msg1)

def test_find_boundary_incomplete():
    buf = b""  # empty
    assert find_boundary(bytearray(buf)) == -1

@pytest.mark.parametrize("buf", [b"\x00", b"\x00\x00\x00\x01\x61"])  # too small or partial
def test_find_boundary_too_small(buf):
    assert find_boundary(bytearray(buf)) == -1
