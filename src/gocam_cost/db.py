"""Build the DuckDB triple-store-over-time and derive per-version metrics.

All per-triple work (skolemization, version diffing, counting) happens here in
SQL over DuckDB's columnar engine — never in Python loops.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import duckdb
import pyarrow as pa

from . import config as C
from .gitdata import Version

MODEL_IRI = "http://model.geneontology.org/"
TITLE_PRED = "http://purl.org/dc/elements/1.1/title"
_TIMING = bool(os.environ.get("GOCAM_TIMING"))


def _ex(con, label: str, sql: str) -> None:
    """Execute a statement, optionally printing its wall time (GOCAM_TIMING=1)."""
    t = time.time()
    con.execute(sql)
    if _TIMING:
        print(f"  [db] {label}: {time.time() - t:.1f}s", file=sys.stderr, flush=True)


def _versions_arrow(versions: list[Version]) -> pa.Table:
    return pa.table({
        "version_id": pa.array(range(len(versions)), pa.int32()),
        "model_id": [v.model_id for v in versions],
        "sha": [v.sha for v in versions],
        "commit_time": pa.array([v.commit_time for v in versions]).cast(pa.string()),
        "blob_oid": [v.blob_oid for v in versions],
    })


def build(versions: list[Version], raw_dir: Path, db_path: Path = C.DUCKDB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    con.execute("PRAGMA preserve_insertion_order=false;")
    con.execute("PRAGMA disable_progress_bar;")
    vtab = _versions_arrow(versions)  # noqa: F841 -- referenced by name in SQL
    con.register("versions_in", vtab)

    # ---- versions table with per-model chronological ordinal + integer model index ----
    # model_idx (a dense integer per model) replaces the 16-char model_id string in
    # the hot diff path, so the window sort compares ints instead of strings.
    _ex(con, "versions", f"""
        CREATE TABLE versions AS
        SELECT version_id, model_id, sha,
               CAST(commit_time AS TIMESTAMP WITH TIME ZONE) AS commit_time, blob_oid,
               row_number() OVER (PARTITION BY model_id
                                  ORDER BY CAST(commit_time AS TIMESTAMP WITH TIME ZONE), version_id) AS ord,
               (dense_rank() OVER (ORDER BY model_id))::INTEGER AS model_idx
        FROM versions_in;
    """)

    # ---- raw triples from the Parquet extract ----
    _ex(con, "load raw", f"CREATE TABLE raw AS SELECT * FROM read_parquet('{raw_dir.as_posix()}/*.parquet');")

    # ---- skolemize owl:Axiom blank nodes deterministically (in SQL) ----
    _ex(con, "bmap (skolem map)", f"""
        CREATE TABLE bmap AS
        WITH ann AS (
            SELECT version_id, subj AS bnode,
                   MAX(obj) FILTER (WHERE pred = '{C.ANNOTATED_SOURCE}')   AS src,
                   MAX(obj) FILTER (WHERE pred = '{C.ANNOTATED_PROPERTY}') AS prop,
                   MAX(obj) FILTER (WHERE pred = '{C.ANNOTATED_TARGET}')   AS tgt
            FROM raw WHERE subj_is_bnode
            GROUP BY version_id, subj
        )
        SELECT version_id, bnode,
               'urn:skolem:axiom:' ||
               md5(coalesce(src,'') || '|' || coalesce(prop,'') || '|' || coalesce(tgt,'')) AS skolem
        FROM ann;
    """)
    # Non-bnode rows (the vast majority) bypass the join entirely; only the ~1M
    # bnode rows join the skolem map. Avoids hashing 24M IRI strings for nothing.
    _ex(con, "triples (skolem join)", """
        CREATE TABLE triples AS
        SELECT version_id, subj AS subject, pred AS predicate, obj AS object, obj_is_literal
        FROM raw WHERE NOT subj_is_bnode
        UNION ALL
        SELECT r.version_id,
               coalesce(b.skolem, 'urn:bnode:' || r.version_id || ':' || r.subj) AS subject,
               r.pred AS predicate, r.obj AS object, r.obj_is_literal
        FROM raw r LEFT JOIN bmap b ON r.version_id = b.version_id AND r.subj = b.bnode
        WHERE r.subj_is_bnode;
    """)

    # ---- per-version metrics: n_triples, added, removed ----
    # Single-pass window functions over each triple's presence across a model's
    # versions (no quadratic self-join). For triple k in model m, tk holds one
    # row per version where k is present; LAG/LEAD over (model_id, k) reveal
    # additions (absent in the previous version) and removals (absent in the next).
    _ex(con, "tk (hash keys)", """
        CREATE TEMP TABLE tk AS
        SELECT t.version_id, v.model_idx, v.ord,
               hash(t.subject, t.predicate, t.object) AS k
        FROM triples t JOIN versions v USING (version_id);
    """)
    _ex(con, "counts", "CREATE TEMP TABLE counts AS SELECT version_id, count(*) AS n_triples FROM tk GROUP BY version_id;")
    _ex(con, "pres (window lag/lead)", """
        CREATE TEMP TABLE pres AS
        SELECT version_id, model_idx, ord, k,
               lag(ord)  OVER w AS prev_ord,
               lead(ord) OVER w AS next_ord
        FROM tk
        WINDOW w AS (PARTITION BY model_idx, k ORDER BY ord);
    """)
    # added at version v: triple present at v but absent in the immediately prior version
    _ex(con, "added", """
        CREATE TEMP TABLE added AS
        SELECT version_id, count(*) AS triples_added
        FROM pres
        WHERE prev_ord IS NULL OR prev_ord < ord - 1
        GROUP BY version_id;
    """)
    # removed at version v (ord o+1): triple present at o, absent at o+1 (and o+1 exists)
    _ex(con, "removed", """
        CREATE TEMP TABLE removed AS
        SELECT vv.version_id, count(*) AS triples_removed
        FROM pres p
        JOIN versions vv ON vv.model_idx = p.model_idx AND vv.ord = p.ord + 1
        WHERE p.next_ord IS DISTINCT FROM p.ord + 1
        GROUP BY vv.version_id;
    """)
    _ex(con, "alter cols", """
        ALTER TABLE versions ADD COLUMN n_triples INTEGER;
        ALTER TABLE versions ADD COLUMN triples_added INTEGER;
        ALTER TABLE versions ADD COLUMN triples_removed INTEGER;
    """)
    _ex(con, "update metrics", """
        UPDATE versions v SET
          n_triples       = c.n_triples,
          triples_added   = coalesce(a.triples_added, 0),
          triples_removed = coalesce(r.triples_removed, 0)
        FROM counts c
        LEFT JOIN added a USING (version_id)
        LEFT JOIN removed r USING (version_id)
        WHERE v.version_id = c.version_id;
    """)

    # ---- models table (title derived from the latest version's dc:title) ----
    _ex(con, "models", f"""
        CREATE TABLE models AS
        WITH titles AS (
            SELECT v.model_id,
                   regexp_replace(t.object, '(^")|("$)', '', 'g') AS title,
                   row_number() OVER (PARTITION BY v.model_id ORDER BY v.ord DESC) AS rn
            FROM triples t JOIN versions v USING (version_id)
            WHERE t.predicate = '{TITLE_PRED}'
              AND t.subject = '{MODEL_IRI}' || v.model_id
        )
        SELECT vv.model_id,
               max(ti.title) AS title,
               count(*) AS n_versions,
               min(vv.commit_time) AS first_seen,
               max(vv.commit_time) AS last_seen,
               max(vv.n_triples) AS max_triples
        FROM versions vv
        LEFT JOIN titles ti ON ti.model_id = vv.model_id AND ti.rn = 1
        GROUP BY vv.model_id;
    """)

    _ex(con, "drop staging", "DROP TABLE raw; DROP TABLE bmap;")
    con.close()
