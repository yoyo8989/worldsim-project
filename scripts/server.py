# server_async_chunks_updated_diff.py
# Asyncio-based TCP server that streams full or diff-compressed terrain chunks
# Integrated full_flag in request header (10 bytes) and per-client last_sent cache for diffs
# License: MIT

import asyncio
import msgpack
import zlib
import signal
import os
import time
from collections import OrderedDict, defaultdict

# Configuration
CHUNK_SIZE = 128            # tiles per chunk dimension
DATA_SOURCE_PATH = 'dem_tiles/'
MAX_RETRIES = 3
RETRY_DELAY = 1.0           # base seconds for retry backoff
MAX_CONCURRENT_SENDS = 4    # per-client send concurrency limit
MAX_CONCURRENT_CLIENTS = 16 # global connections limit
CACHE_MAX_SIZE = 100        # max LRU entries
CACHE_MAX_AGE = 300         # seconds TTL for cache entries
COMPRESSION_LEVEL = 6       # zlib level (1-9)
REQUEST_HEADER_SIZE = 10    # bytes: 1(full_flag)+4(cx)+4(cy)+1(lod)

# Diff utilities from msgpack_diff.gd equivalent in Python
def compute_diff(old, new):
    if isinstance(old, dict) and isinstance(new, dict):
        diff = {}
        for k, v in new.items():
            if k not in old or old[k] != v:
                diff[k] = v
        for k in old:
            if k not in new:
                diff[k] = None
        return diff
    if isinstance(old, list) and isinstance(new, list):
        diffs = []
        min_len = min(len(old), len(new))
        for i in range(min_len):
            if old[i] != new[i]: diffs.append({'index': i, 'value': new[i]})
        for i in range(min_len, len(new)): diffs.append({'index': i, 'value': new[i]})
        return diffs
    return new if old != new else None

def pack_and_compress(data):
    packed = msgpack.packb(data, use_bin_type=True)
    compressed = zlib.compress(packed, level=COMPRESSION_LEVEL)
    header = len(compressed).to_bytes(4, 'big')
    return header + compressed

# Per-client last sent store: {client_id: {(cx,cy,lod): chunk_data}}
_last_sent = defaultdict(dict)
_compressed_cache = OrderedDict()
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CLIENTS)
to_shutdown = False

# Load chunk full data
def load_chunk(cx, cy):
    path = os.path.join(DATA_SOURCE_PATH, f"{cx}_{cy}.dat")
    if os.path.isfile(path):
        return msgpack.unpackb(open(path, 'rb').read(), raw=False)
    return [[0.0]*CHUNK_SIZE for _ in range(CHUNK_SIZE)]

# Request retry with backoff
def exp_backoff(attempt): return min(RETRY_DELAY * (2**attempt), 10.0)

async def handle_client(reader, writer):
    cid = id(writer)
    await _semaphore.acquire()
    try:
        while not to_shutdown:
            hdr = await reader.readexactly(REQUEST_HEADER_SIZE)
            full_flag = hdr[0]
            cx = int.from_bytes(hdr[1:5], 'big', signed=True)
            cy = int.from_bytes(hdr[5:9], 'big', signed=True)
            lod = hdr[9] / 255.0
            # get base and new
            new_data = load_chunk(cx, cy)
            if lod < 1.0:
                factor = max(int(1/lod),1)
                new_data = [[new_data[y*factor][x*factor] for x in range(0, CHUNK_SIZE, factor)] for y in range(0, CHUNK_SIZE, factor)]
            base = _last_sent[cid].get((cx,cy,lod), None)
            if full_flag == 0 and base is not None:
                diff = compute_diff(base, new_data)
                data_to_send = diff if diff is not None else {}
            else:
                data_to_send = new_data
            # pack & send
            payload = pack_and_compress(data_to_send)
            for attempt in range(MAX_RETRIES):
                try:
                    writer.write(payload)
                    await writer.drain()
                    break
                except Exception:
                    await asyncio.sleep(exp_backoff(attempt))
            _last_sent[cid][(cx,cy,lod)] = new_data
    except asyncio.IncompleteReadError:
        pass
    finally:
        writer.close(); await writer.wait_closed(); _semaphore.release()

async def server_loop():
    server = await asyncio.start_server(handle_client, '0.0.0.0', 6000, reuse_address=True, reuse_port=True)
    async with server: await server.serve_forever()

def _ask_shutdown(): global to_shutdown; to_shutdown=True

def main():
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM): loop.add_signal_handler(sig, _ask_shutdown)
    loop.run_until_complete(server_loop())
    loop.close()

if __name__ == '__main__': main()
