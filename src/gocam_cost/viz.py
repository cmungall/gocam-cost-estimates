"""Plotting for the examples-only edit-pattern gallery.

Each representative model gets a row: x = commit time, stems show edit SIZE per
save (triples added up/green, removed down/red), and a twin line shows the
cumulative triple count ("the model growing").
"""
from __future__ import annotations

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


def plot_time_histogram(curation: pd.DataFrame):
    """Distribution of adjusted active editing time for multi-save models."""
    import matplotlib.pyplot as plt

    multi = curation[curation.n_saves >= 2]
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ax.hist(multi.adj_min_60m.clip(upper=240), bins=40, color="#2a6f97")
    ax.set_xlabel("adjusted active editing time per model (min, 60-min gap, capped at 240)")
    ax.set_ylabel("models")
    ax.set_title(f"Curation time per actively-curated GO-CAM (n={len(multi):,})")
    fig.tight_layout()
    return fig


def plot_gallery(versions: pd.DataFrame, examples: pd.DataFrame):
    """Return a matplotlib Figure: one timeline row per example model."""
    reps = examples.sort_values(["pattern", "total_churn"], ascending=[True, False])
    n = len(reps)
    fig, axes = plt.subplots(n, 1, figsize=(11, 1.7 * n), squeeze=False)
    axes = axes[:, 0]

    for ax, (_, ex) in zip(axes, reps.iterrows()):
        v = versions[versions.model_id == ex.model_id].sort_values("commit_time")
        t = pd.to_datetime(v["commit_time"])
        added = v["triples_added"].to_numpy()
        removed = v["triples_removed"].to_numpy()

        ax.vlines(t, 0, added, color="#2a9d4a", lw=1.6, alpha=0.9)
        ax.vlines(t, 0, -removed, color="#c0392b", lw=1.6, alpha=0.9)
        ax.axhline(0, color="#bbbbbb", lw=0.6)

        ax2 = ax.twinx()
        ax2.plot(t, v["n_triples"], color="#34495e", lw=1.1, alpha=0.7)
        ax2.set_ylim(bottom=0)
        ax2.set_ylabel("triples", fontsize=7, color="#34495e")
        ax2.tick_params(labelsize=6, colors="#34495e")

        title = str(ex.title)[:46] if pd.notna(ex.title) else ex.model_id
        ax.set_title(
            f"[{ex.pattern}]  {title}   "
            f"(saves={int(ex.n_saves)}, churn={int(ex.total_churn)}, "
            f"active≈{ex.active_min_60m:.0f} min, span={int(ex.calendar_span_days)} d)",
            fontsize=8, loc="left",
        )
        ax.tick_params(labelsize=6)
        ax.set_ylabel("Δ triples", fontsize=7)
        ax.margins(x=0.01)

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.suptitle("GO-CAM edit patterns — green = triples added, red = removed, line = total size",
                 fontsize=10, y=1.0)
    fig.tight_layout()
    return fig
