# tests/test_terrain_loader.py
# Adjusted to mock StreamPeerTCP import correctly
import sys
import pytest
# Add project root so that TerrainLoader can be imported
sys.path.append('.')

from TerrainLoader import TerrainLoader, StreamPeerTCP
from common_utils import CommonUtils
import msgpack, zlib

class DummyPeer:
    def __init__(self, responses):
        self.responses = responses
        self.sent = bytearray()
    def connect_to_host(self, host, port): return 0
    def set_no_delay(self, val): pass
    def put_data(self, data): self.sent.extend(data)
    def get_data(self, size): return self.responses.pop(0)
    def get_status(self): return StreamPeerTCP.STATUS_CONNECTED

@pytest.fixture(autouse=True)
def patch_streampeer(monkeypatch):
    # Monkey-patch the StreamPeerTCP constructor in TerrainLoader
    import TerrainLoader as tl_mod
    monkeypatch.setattr(tl_mod, 'StreamPeerTCP', lambda: DummyPeer(responses.copy()))

# Helper to build full payload
def make_full_response(data):
    packed = msgpack.packb(data, use_bin_type=True)
    compressed = zlib.compress(packed)
    payload = bytes([1]) + compressed
    return len(payload).to_bytes(4,'big') + payload

@pytest.mark.asyncio
async def test_full_request_and_error_handling():
    # Prepare loader and simulate a normal full response
    loader = TerrainLoader.new()
    global responses
    data = [0.1, 0.2, 0.3, 0.4]
    responses = [make_full_response(data)]

    # Request chunk and listen
    loader.request_chunk(1, 2, 1.0, 1)
    await loader._listen_loop()
    # Verify terrain_ready
    assert 'terrain_ready' in loader.signals
    arr, dim = loader.signals['terrain_ready']
    assert list(arr) == data
    assert dim == 2

    # Test incomplete header error
    responses = [b'']
    loader = TerrainLoader.new()
    loader.request_chunk(0, 0, 1.0, 1)
    await loader._listen_loop()
    assert 'terrain_error' in loader.signals
