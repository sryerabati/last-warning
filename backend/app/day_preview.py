"""Persistent campus-day cache and streaming delivery for a hosted origin."""
import asyncio
import gzip
import hashlib
import json
import os
import tempfile
import zlib
from pathlib import Path

from fastapi.responses import StreamingResponse

from .simulation.campus_engine import VERSION as CAMPUS_VERSION
from .simulation.campus_life import DAY_VERSION, campus_day


def cache_path(root, config):
    key = [CAMPUS_VERSION, DAY_VERSION, config.population, config.seed,
           config.campus_day_type, config.transit_enabled]
    digest = hashlib.sha256(json.dumps(key, separators=(",", ":")).encode()).hexdigest()
    return Path(root) / "day-cache" / f"{digest}.json.gz"


def cached_campus_day(root, config):
    path = cache_path(root, config)
    if path.is_file():
        try:
            with gzip.open(path, "rt") as source:
                return json.load(source)
        except (OSError, ValueError):
            pass
    value = campus_day(config.population, config.seed, config.disaster_type,
                       campus_day_type=config.campus_day_type, transit_enabled=config.transit_enabled)
    path.parent.mkdir(exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    os.close(descriptor)
    try:
        with gzip.open(temporary, "wt", compresslevel=4) as output:
            json.dump(value, output, separators=(",", ":"), allow_nan=False)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return value


def streamed_campus_day(root, config):
    async def stream():
        task = asyncio.create_task(asyncio.to_thread(cached_campus_day, root, config))
        task.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
        compressor = zlib.compressobj(level=4, wbits=31)
        # JSON allows leading whitespace. Flushed gzip chunks keep the request
        # responsive while the CPU engine prepares a complete physical day.
        yield compressor.compress(b" ") + compressor.flush(zlib.Z_SYNC_FLUSH)
        while not task.done():
            await asyncio.wait([task], timeout=10)
            if not task.done():
                yield compressor.compress(b" ") + compressor.flush(zlib.Z_SYNC_FLUSH)
        try:
            value = await task
        except Exception:
            value = {"_preview_error": "The campus day could not be prepared. Try a smaller population or reconnect."}
        encoded = await asyncio.to_thread(json.dumps, value, separators=(",", ":"), allow_nan=False)
        for offset in range(0, len(encoded), 256 * 1024):
            yield compressor.compress(encoded[offset:offset + 256 * 1024].encode())
        yield compressor.flush()

    return StreamingResponse(stream(), media_type="application/json", headers={
        "Content-Encoding": "gzip", "Cache-Control": "private, no-store", "X-Accel-Buffering": "no"})
