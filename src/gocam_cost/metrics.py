"""Curation-time metrics derived from per-model save-event timestamps.

Save events come from git commit times (~5-min resolution). We group them into
sessions (wall-clock gaps) and campaigns (calendar-day gaps). Measured active
time is a lower bound; the adjusted estimate credits one sync interval per
session for the unobserved ramp before the first save / tail after the last.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from . import config as C


def _sessions(times: list[datetime], gap: timedelta) -> list[tuple[datetime, datetime]]:
    out = []
    s = e = times[0]
    for t in times[1:]:
        if t - e > gap:
            out.append((s, e))
            s = t
        e = t
    out.append((s, e))
    return out


def _campaigns(days: list[datetime], gap_days: int) -> int:
    ds = sorted({d.date() for d in days})
    n = 1
    for a, b in zip(ds, ds[1:]):
        if (b - a).days > gap_days:
            n += 1
    return n


def compute(db_path: Path = C.DUCKDB_PATH) -> pd.DataFrame:
    """Return one row of curation metrics per model."""
    con = duckdb.connect(str(db_path), read_only=True)
    vt = con.execute("""
        SELECT model_id, commit_time,
               coalesce(triples_added, 0)   AS added,
               coalesce(triples_removed, 0) AS removed,
               n_triples
        FROM versions ORDER BY model_id, commit_time
    """).fetchdf()
    meta = con.execute("SELECT model_id, title, state FROM models").fetchdf()
    con.close()

    rows = []
    for model_id, g in vt.groupby("model_id", sort=False):
        times = list(pd.to_datetime(g["commit_time"]).dt.to_pydatetime())
        days = times
        row = {
            "model_id": model_id,
            "n_saves": len(times),
            "n_active_days": len({t.date() for t in times}),
            "first": times[0],
            "last": times[-1],
            "calendar_span_days": (times[-1] - times[0]).days,
            "n_versions": len(g),
            "max_triples": int(g["n_triples"].max()),
            "total_added": int(g["added"].sum()),
            "total_removed": int(g["removed"].sum()),
            "total_churn": int(g["added"].sum() + g["removed"].sum()),
        }
        for gmin in C.FINE_GAPS_MIN:
            ss = _sessions(times, timedelta(minutes=gmin))
            active = sum((e - s).total_seconds() for s, e in ss) / 60.0
            row[f"sessions_{gmin}m"] = len(ss)
            row[f"active_min_{gmin}m"] = round(active, 1)
            row[f"adj_min_{gmin}m"] = round(active + C.SYNC_INTERVAL_MIN * len(ss), 1)
        for gd in C.DAY_GAPS:
            row[f"campaigns_{gd}d"] = _campaigns(days, gd)
        rows.append(row)

    from .true_gocams import fetch_index
    idx = fetch_index()
    df = pd.DataFrame(rows).merge(meta, on="model_id", how="left")
    df["is_true_gocam"] = df.model_id.isin(set(idx.model_id))
    return df.merge(idx[["model_id", "n_activities", "taxon", "longest_path"]],
                    on="model_id", how="left")


def cohort_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Headline medians/means over the canonical **True GO-CAM** set.

    A True GO-CAM is defined by the GO production pipeline (production status +
    connected causal activity graph + evidence); we flag membership against the
    published go-cam-browser index. Curation time is only measurable for those
    with >=2 individual (non-bulk) saves in the window.
    """
    tg = df[df.is_true_gocam]
    cohorts = {
        "true_gocam_measurable_>=2saves": tg[tg.n_saves >= 2],   # headline
        "true_gocam_substantial_>=5": tg[tg.n_saves >= 5],
        "true_gocam_with_curation": tg,                          # incl. single in-window edit
    }
    metrics = ["n_saves", "n_active_days", "calendar_span_days",
               "active_min_60m", "adj_min_60m", "sessions_60m",
               "n_activities", "total_churn"]
    out = []
    for name, c in cohorts.items():
        rec = {"cohort": name, "n_models": len(c)}
        for m in metrics:
            rec[f"{m}_median"] = round(float(c[m].median()), 1)
            rec[f"{m}_mean"] = round(float(c[m].mean()), 1)
        out.append(rec)
    return pd.DataFrame(out)
