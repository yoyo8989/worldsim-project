# test_server.py
# Updated to directly await handle_client and test abnormal flows
import asyncio
import pytest
import msgpack
import zlib
from server import handle_client, compute_diff, pack_and_compress, find_boundary
from io import BytesIO

class DummyWriter:
    def __init__(self):
        self.buffer = bytearray()
        self.closed = False
    def write(self, data):
        self.buffer.extend(data)
    async def drain(self):
        pass
    def get_extra_info(self, name):
        return ('127.0.0.1', 6000)
    def close(self):
        self.closed = True
    async def wait_closed(self):
        pass

class DummyReader:
    def __init__(self, data):
        self.buffer = BytesIO(data)
    async def readexactly(self, n):
        data = self.buffer.read(n)
        if len(data) < n:
            raise asyncio.IncompleteReadError(partial=data, expected=n)
        return data
    def at_eof(self):
        return self.buffer.tell() == len(self.buffer.getvalue())

# Helper to build header+payload
def build_message(full_flag, cx, cy, lod, content_data):
    packed = msgpack.packb(content_data, use_bin_type=True)
    compressed = zlib.compress(packed)
    payload = bytes([full_flag]) + compressed
    header = len(payload).to_bytes(4, 'big')
    return header + payload

@pytest.mark.asyncio
async def test_handle_client_full():
    # Normal full request
    data = [1,2,3]
    msg = build_message(1, 0, 0, 1.0, data)
    reader = DummyReader(msg)
    writer = DummyWriter()
    # Direct call with timeout
    await asyncio.wait_for(handle_client(reader, writer), timeout=0.1)
    assert writer.closed
    # Verify that buffer starts with full payload
    assert writer.buffer.startswith(msg[4:])

@pytest.mark.asyncio
async def test_handle_client_diff():
    # Full then diff
    base = [0,0,0]
    new = [0,5,0]
    msg1 = build_message(1,0,0,1.0, base)
    msg2 = build_message(0,0,0,1.0, new)
    reader = DummyReader(msg1 + msg2)
    writer = DummyWriter()
    # Await two iterations
    await asyncio.wait_for(handle_client(reader, writer), timeout=0.1)
    # Two payloads written
    # The writer.buffer includes both writes sequentially
    # Validate that second write contains diff compressed
    # Decompress second payload
    full_len = int.from_bytes(writer.buffer[:4], 'big')
    # skip first payload
    idx = 4 + full_len
    second_header = writer.buffer[idx:idx+4]
    diff_len = int.from_bytes(second_header, 'big')
    diff_compressed = writer.buffer[idx+4:idx+4+diff_len]
    diff_data = msgpack.unpackb(zlib.decompress(diff_compressed), raw=False)
    assert diff_data == [{'index':1,'value':5}]

@pytest.mark.asyncio
async def test_handle_client_incomplete_header():
    reader = DummyReader(b'')
    writer = DummyWriter()
    await asyncio.wait_for(handle_client(reader, writer), timeout=0.1)
    assert writer.closed

@pytest.mark.asyncio
async def test_handle_client_corrupted_payload():
    # Header OK but payload bad
    header = (1).to_bytes(1,'big') + (0).to_bytes(4,'big',signed=True) + (0).to_bytes(4,'big',signed=True) + (255).to_bytes(1,'big')
    msg = len(header).to_bytes(4,'big') + header
    reader = DummyReader(msg)
    writer = DummyWriter()
    await asyncio.wait_for(handle_client(reader, writer), timeout=0.1)
    assert writer.closed
