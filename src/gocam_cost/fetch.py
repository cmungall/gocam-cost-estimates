"""Fetch raw model .ttl contents over HTTP, cached on disk by blob oid.

Benchmarked at ~1.4 min for the full ~26k-version cohort at concurrency 32.
Content-addressed by git blob oid, so re-runs and partial runs are free.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from . import config as C
from .gitdata import Version


def _cache_path(blob_oid: str) -> Path:
    return C.BLOB_CACHE / blob_oid[:2] / f"{blob_oid}.ttl"


def cached_bytes(blob_oid: str) -> bytes | None:
    p = _cache_path(blob_oid)
    return p.read_bytes() if p.exists() else None


async def _fetch_one(client: httpx.AsyncClient, v: Version, sem: asyncio.Semaphore,
                     missing: list, retries: int = 4) -> None:
    dest = _cache_path(v.blob_oid)
    if dest.exists():
        return
    url = f"{C.RAW_BASE}/{v.sha}/models/{v.model_id}.ttl"
    async with sem:
        for attempt in range(retries):
            try:
                resp = await client.get(url)
            except httpx.HTTPError:
                await asyncio.sleep(2 ** attempt)
                continue
            if resp.status_code == 200:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(resp.content)
                return
            if resp.status_code == 404:
                missing.append(v.blob_oid)   # stray deletion/edge case; skip
                return
            if resp.status_code in (429, 500, 502, 503, 504):
                await asyncio.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
        missing.append(v.blob_oid)


async def _fetch_all(versions: list[Version], concurrency: int, missing: list) -> None:
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=30) as client:
        await asyncio.gather(*[_fetch_one(client, v, sem, missing) for v in versions])


def fetch_versions(versions: list[Version], concurrency: int = 32) -> tuple[int, list[str]]:
    """Ensure every version's .ttl is cached. Returns (count_attempted, missing_oids)."""
    needed = [v for v in versions if not _cache_path(v.blob_oid).exists()]
    missing: list[str] = []
    if needed:
        asyncio.run(_fetch_all(needed, concurrency, missing))
    return len(needed), missing
