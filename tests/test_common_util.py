import sys
import pytest
sys.path.append('res://scripts')

from common_utils import CommonUtils

class DummyNode:
    def __init__(self):
        self.emitted = []
    def has_signal(self, name): return name == 'test_signal'
    def callv(self, method_name, args):
        # test 用に emit_signal を呼び出し
        if method_name == "emit_signal":
            self.emit_signal(args[0], *args[1:])
    def emit_signal(self, name, *args):
        self.emitted.append((name, args))

@pytest.mark.parametrize("value", [0, 1, 127, -1, 2**31-1, -2**31])
def test_int32_bytes_roundtrip(value):
    b = CommonUtils.int32_to_bytes(value)
    assert isinstance(b, bytes) or hasattr(b, 'size')
    assert CommonUtils.bytes_to_int32(b) == value

def test_bytes_to_int32_too_small(caplog):
    small = bytearray([0,1])
    result = CommonUtils.bytes_to_int32(small)
    assert result == 0
    assert 'buffer too small' in caplog.text

@pytest.mark.parametrize("flag,cx,cy,lod", [
    (0, 0, 0, 0.0),
    (1, -1, 1, 0.5),
    (1, 12345, -12345, 1.0)
])
def test_build_request_header(flag, cx, cy, lod):
    hdr = CommonUtils.build_request_header(flag, cx, cy, lod)
    assert hasattr(hdr, 'size') and hdr.size() == 10
    assert hdr[0] == flag
    assert hdr[9] == int(lod * 255)
    # extract cx, cy
    cx_rt = CommonUtils.bytes_to_int32(hdr[1:5])
    cy_rt = CommonUtils.bytes_to_int32(hdr[5:9])
    assert cx_rt == cx
    assert cy_rt == cy

@pytest.mark.parametrize("args", [[], [1], [1,2,'a']])
def test_safe_emit(monkeypatch, caplog, args):
    node = DummyNode()
    # successful emit
    CommonUtils.safe_emit(node, 'test_signal', args)
    assert node.emitted and node.emitted[0] == ('test_signal',) + tuple(args)

    # missing signal
    node.emitted.clear()+    CommonUtils.safe_emit(node, 'no_signal', args)
+    assert 'not found' in caplog.tex
+    assert node.emitted == []
