import sys
import builtins
from types import SimpleNamespace
import pytest

# Add project paths if needed
# sys.path.append('.')
# sys.path.append('res://scripts')

# Mock Godot-specific types for pytest
Vector2i = lambda x, y: SimpleNamespace(x=x, y=y)
PackedFloat32Array = list  # use Python list to simulate PackedFloat32Array behavior
PackedByteArray = bytearray  # use bytearray for PackedByteArray

# Mock StreamPeerTCP with minimal attributes
class MockStreamPeerTCP(SimpleNamespace):
    STATUS_CONNECTED = 1
    STATUS_CONNECTING = 0
    def __init__(self):
        super().__init__()
    def set_no_delay(self, val):
        pass
    def connect_to_host(self, host, port):
        return self.STATUS_CONNECTED
    def get_status(self):
        return self.STATUS_CONNECTED

# Inject mocks into globals so test modules can import directly
@pytest.fixture(autouse=True)
def godot_mocks(monkeypatch):
    # Mock Vector2i
    monkeypatch.setitem(builtins.__dict__, 'Vector2i', Vector2i)
    # Mock PackedByteArray and PackedFloat32Array
    monkeypatch.setitem(builtins.__dict__, 'PackedByteArray', PackedByteArray)
    monkeypatch.setitem(builtins.__dict__, 'PackedFloat32Array', PackedFloat32Array)
    # Mock StreamPeerTCP class in client modules
    monkeypatch.setitem(sys.modules, 'TerrainLoader.StreamPeerTCP', MockStreamPeerTCP)
    monkeypatch.setitem(sys.modules, 'TerrainAscii.StreamPeerTCP', MockStreamPeerTCP)
