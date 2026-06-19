"""Parse cached model .ttl into raw triple rows (Rust-fast via pyoxigraph).

Writes a Parquet dataset of raw triples keyed by an integer version_id. Blank
nodes are kept with their per-file labels (unique within a version); they are
skolemized later in DuckDB SQL. Objects are stored as canonical strings so that
triple identity is exact across versions (literals include datatype/language).
"""
from __future__ import annotations

import io
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pyoxigraph as ox

from .fetch import cached_bytes
from .gitdata import Version

_SCHEMA = pa.schema([
    ("version_id", pa.int32()),
    ("subj", pa.string()),
    ("subj_is_bnode", pa.bool_()),
    ("pred", pa.string()),
    ("obj", pa.string()),
    ("obj_is_literal", pa.bool_()),
])


def triples_from_bytes(data: bytes):
    """Yield (subj, subj_is_bnode, pred, obj, obj_is_literal) from Turtle bytes."""
    for q in ox.parse(io.BytesIO(data), format=ox.RdfFormat.TURTLE):
        s, o = q.subject, q.object
        if isinstance(o, ox.Literal):
            obj, obj_is_literal = str(o), True       # canonical "v"^^<dt> / "v"@lang
        else:
            obj, obj_is_literal = o.value, False     # NamedNode IRI
        yield (s.value, isinstance(s, ox.BlankNode), q.predicate.value, obj, obj_is_literal)


def _triples(blob_oid: str):
    """Yield triple rows for one cached version."""
    data = cached_bytes(blob_oid)
    if data is None:
        raise FileNotFoundError(f"blob {blob_oid} not cached; run fetch first")
    yield from triples_from_bytes(data)


def extract_to_parquet(versions: list[Version], out_dir: Path, flush_rows: int = 1_000_000) -> int:
    """Parse all versions to a Parquet dataset under out_dir. Returns triple count.

    version_id is the index of the version in `versions`. Flushes a Parquet part
    whenever ~flush_rows triples have accumulated, to bound memory.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("part-*.parquet"):
        old.unlink()
    total = 0
    part = 0
    cols: list[list] = [[], [], [], [], [], []]

    def flush() -> None:
        nonlocal part, cols
        if not cols[0]:
            return
        table = pa.table({name: pa.array(col, type=_SCHEMA.field(name).type)
                          for name, col in zip(_SCHEMA.names, cols)})
        pq.write_table(table, out_dir / f"part-{part:05d}.parquet")
        part += 1
        cols = [[], [], [], [], [], []]

    for vid, v in enumerate(versions):
        for subj, sb, pred, obj, ol in _triples(v.blob_oid):
            cols[0].append(vid)
            cols[1].append(subj)
            cols[2].append(sb)
            cols[3].append(pred)
            cols[4].append(obj)
            cols[5].append(ol)
            total += 1
        if len(cols[0]) >= flush_rows:
            flush()
    flush()
    return total
