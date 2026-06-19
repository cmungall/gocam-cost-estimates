"""Generate a self-contained interactive marimo notebook for GitHub Pages.

The published notebook is exported to WASM (runs in-browser via Pyodide), so it
must NOT import `gocam_cost` or read local files. We therefore embed the
production data inline (gzip + base64 CSV — no pyarrow needed in the browser)
and inline the small plotting helpers.
"""
from __future__ import annotations

import base64
import gzip
from pathlib import Path

import pandas as pd

from . import config as C
from . import patterns

NOTEBOOK = C.ROOT / "notebooks" / "cost_estimates.py"


def _b64(df: pd.DataFrame) -> str:
    return base64.b64encode(gzip.compress(df.to_csv(index=False).encode())).decode()


def generate(out: Path = NOTEBOOK) -> Path:
    cm = pd.read_parquet(C.DATA / "curation_metrics.parquet")
    cm = cm[cm.state == "production"].copy()
    cm["pattern"] = patterns.classify(cm)
    cm["title"] = cm["title"].fillna("")
    keep = ["model_id", "title", "pattern", "n_saves", "n_active_days",
            "calendar_span_days", "sessions_60m", "active_min_60m", "adj_min_60m",
            "max_triples", "total_churn", "total_added", "total_removed", "first", "last"]
    cm = cm[keep]

    v = pd.read_parquet(C.DATA / "versions.parquet")
    v = v[v.model_id.isin(set(cm.model_id))][
        ["model_id", "commit_time", "triples_added", "triples_removed", "n_triples"]]

    nb = (_TEMPLATE
          .replace("__MODELS_B64__", _b64(cm))
          .replace("__VERSIONS_B64__", _b64(v))
          .replace("__N_MODELS__", str(len(cm)))
          .replace("__N_VERSIONS__", str(len(v))))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(nb)
    return out


# The notebook is plain text with sentinels substituted above. Braces are literal.
_TEMPLATE = r'''import marimo

__generated_with = "0.23.10"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import base64, gzip, io
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import marimo as mo

    def _load(b64):
        return pd.read_csv(io.BytesIO(gzip.decompress(base64.b64decode(b64))))

    MODELS = _load("__MODELS_B64__")
    VERSIONS = _load("__VERSIONS_B64__")
    VERSIONS["commit_time"] = pd.to_datetime(VERSIONS["commit_time"], utc=True)
    return MODELS, VERSIONS, mdates, mo, np, pd, plt


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # GO-CAM curation cost estimates

        How much **curation effort** goes into GO-CAM models, derived from
        `geneontology/noctua-models` git history. The minerva→GitHub bot commits
        every **~5 minutes**, so each commit touching a model is a **save event at
        ~5-min resolution**. We keep only **production** native GO-CAMs (last 2
        years), group save events into sessions, and measure **edit size** as
        triples added/removed per save (from a DuckDB triple-store-over-time).

        *Active editing time is a lower bound — it excludes literature reading and
        planning done outside Noctua.*
        """
    )
    return


@app.cell(hide_code=True)
def _(MODELS, mo, pd):
    def _summ(d):
        return {
            "models": len(d),
            "active min (median)": round(d.active_min_60m.median(), 1),
            "active min (mean)": round(d.active_min_60m.mean(), 1),
            "sessions (median)": round(d.sessions_60m.median(), 1),
            "active days (median)": round(d.n_active_days.median(), 1),
            "span days (median)": round(d.calendar_span_days.median(), 1),
            "triples (median)": round(d.max_triples.median(), 1),
        }
    summary = pd.DataFrame({
        "all production": _summ(MODELS),
        "≥2 saves (real curation)": _summ(MODELS[MODELS.n_saves >= 2]),
        "substantial (≥5 saves)": _summ(MODELS[MODELS.n_saves >= 5]),
    }).T
    mo.vstack([mo.md("## How long does a GO-CAM take to curate?"), mo.ui.table(summary, selection=None)])
    return


@app.cell(hide_code=True)
def _(MODELS, mo, plt):
    multi = MODELS[MODELS.n_saves >= 2]
    fig_h, ax_h = plt.subplots(figsize=(8, 3.2))
    ax_h.hist(multi.adj_min_60m.clip(upper=240), bins=40, color="#2a6f97")
    ax_h.set_xlabel("adjusted active editing time per model (min, capped 240)")
    ax_h.set_ylabel("models")
    ax_h.set_title(f"Curation time per actively-curated GO-CAM (n={len(multi):,})")
    fig_h.tight_layout()
    mo.vstack([mo.md("Distribution across the {:,} production models with ≥2 saves:".format(len(multi))), fig_h])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ## Explore individual models

        Filter the table, then **click a row** to see that model's edit timeline
        below — green = triples added, red = removed, line = total model size.
        """
    )
    return


@app.cell(hide_code=True)
def _(MODELS, mo):
    search = mo.ui.text(placeholder="filter by title…", full_width=True)
    min_saves = mo.ui.slider(1, int(MODELS.n_saves.max()), value=2, label="min saves", show_value=True)
    pattern = mo.ui.dropdown(
        ["(any)", "blitz", "revisit_burst", "slow_burn", "stub"], value="(any)", label="pattern")
    mo.hstack([search, min_saves, pattern], justify="start", gap=2)
    return min_saves, pattern, search


@app.cell(hide_code=True)
def _(MODELS, min_saves, mo, pattern, search):
    d = MODELS[MODELS.n_saves >= min_saves.value]
    if search.value:
        d = d[d.title.str.contains(search.value, case=False, na=False)]
    if pattern.value != "(any)":
        d = d[d.pattern == pattern.value]
    cols = ["model_id", "title", "pattern", "n_saves", "active_min_60m",
            "total_churn", "max_triples", "calendar_span_days"]
    table = mo.ui.table(
        d[cols].sort_values("total_churn", ascending=False),
        selection="single", page_size=12, label=f"{len(d):,} models")
    table
    return (table,)


@app.cell(hide_code=True)
def _(VERSIONS, mdates, mo, plt, table):
    rows = table.value
    mid = None
    if rows is not None and len(rows) > 0:
        mid = (rows["model_id"].iloc[0] if hasattr(rows, "iloc") else rows[0]["model_id"])
    if mid is None:
        out = mo.md("*Select a model in the table above to see its edit timeline.*")
    else:
        v = VERSIONS[VERSIONS.model_id == mid].sort_values("commit_time")
        fig, ax = plt.subplots(figsize=(10, 3.2))
        ax.vlines(v.commit_time, 0, v.triples_added, color="#2a9d4a", lw=1.6)
        ax.vlines(v.commit_time, 0, -v.triples_removed, color="#c0392b", lw=1.6)
        ax.axhline(0, color="#bbb", lw=0.6)
        ax.set_ylabel("Δ triples / save")
        ax2 = ax.twinx()
        ax2.plot(v.commit_time, v.n_triples, color="#34495e", lw=1.2, alpha=0.7)
        ax2.set_ylabel("total triples", color="#34495e")
        ax2.set_ylim(bottom=0)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.set_title(f"{mid} — {len(v)} saves", fontsize=10)
        fig.tight_layout()
        out = mo.vstack([mo.md(f"### `{mid}`"), fig])
    out
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ---
        *True native GO-CAMs only (gene-centric/import models excluded). Bulk
        pipeline commits dropped. Saves within one 5-min window collapse. Active
        time is a lower bound on real effort. Source:*
        [github.com/cmungall/gocam-cost-estimates](https://github.com/cmungall/gocam-cost-estimates)
        """
    )
    return


if __name__ == "__main__":
    app.run()
'''
