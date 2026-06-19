"""Generate a static HTML report for GitHub Pages (docs/)."""
from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")

from . import config as C
from . import metrics, viz

COHORT_LABELS = {
    "all_recent_native": "All recent native GO-CAMs",
    "multi_save_>=2": "Multi-save (≥2 commits)",
    "substantial_>=5": "Substantial (≥5 commits)",
}


def _summary_html(summary: pd.DataFrame) -> str:
    rows = []
    for _, r in summary.iterrows():
        rows.append(
            f"<tr><td>{COHORT_LABELS.get(r.cohort, r.cohort)}</td>"
            f"<td>{int(r.n_models):,}</td>"
            f"<td>{r['active_min_60m_median']:.0f} / {r['adj_min_60m_median']:.0f} min</td>"
            f"<td>{r['active_min_60m_mean']:.0f} / {r['adj_min_60m_mean']:.0f} min</td>"
            f"<td>{r['sessions_60m_median']:.0f}</td>"
            f"<td>{r['n_active_days_median']:.0f}</td>"
            f"<td>{r['calendar_span_days_median']:.0f} d</td>"
            f"<td>{r['max_triples_median']:.0f}</td></tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Cohort</th><th>Models</th>"
        "<th>Active time, median<br>(measured / adjusted)</th>"
        "<th>Active time, mean<br>(measured / adjusted)</th>"
        "<th>Sessions</th><th>Active days</th><th>Span</th><th>Triples</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _examples_html(examples: pd.DataFrame) -> str:
    rows = []
    for _, r in examples.sort_values(["pattern", "total_churn"], ascending=[True, False]).iterrows():
        rows.append(
            f"<tr><td><code>{r.pattern}</code></td><td>{str(r.title)[:60]}</td>"
            f"<td>{int(r.n_saves)}</td><td>{int(r.total_churn)}</td>"
            f"<td>{r.active_min_60m:.0f} min</td><td>{int(r.calendar_span_days)} d</td>"
            f"<td><code>{r.model_id}</code></td></tr>"
        )
    return (
        "<table><thead><tr><th>Pattern</th><th>Title</th><th>Saves</th>"
        "<th>Churn</th><th>Active</th><th>Span</th><th>Model</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )


def generate(out_dir: Path | None = None) -> Path:
    out_dir = out_dir or (C.ROOT / "docs")
    out_dir.mkdir(parents=True, exist_ok=True)

    curation = pd.read_parquet(C.DATA / "curation_metrics.parquet")
    versions = pd.read_parquet(C.DATA / "versions.parquet")
    examples = pd.read_parquet(C.DATA / "examples.parquet")
    summary = metrics.cohort_summary(curation)

    viz.plot_time_histogram(curation).savefig(out_dir / "curation_time.png", dpi=130, bbox_inches="tight")
    viz.plot_gallery(versions, examples).savefig(out_dir / "gallery.png", dpi=130, bbox_inches="tight")

    n_models = len(curation)
    total_hours = curation["adj_min_60m"].sum() / 60.0
    html = _PAGE.format(
        n_models=f"{n_models:,}",
        n_versions=f"{len(versions):,}",
        total_hours=f"{total_hours:,.0f}",
        summary_table=_summary_html(summary),
        examples_table=_examples_html(examples),
    )
    (out_dir / "index.html").write_text(html)
    (out_dir / ".nojekyll").write_text("")
    return out_dir


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GO-CAM curation cost estimates</title>
<style>
  body {{ font: 16px/1.55 -apple-system, system-ui, sans-serif; max-width: 920px;
         margin: 2rem auto; padding: 0 1rem; color: #222; }}
  h1 {{ margin-bottom: .2rem; }} .sub {{ color: #666; margin-top: 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 14px; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 9px; text-align: left; }}
  th {{ background: #f5f7fa; }} code {{ font-size: 12px; }}
  img {{ max-width: 100%; border: 1px solid #eee; border-radius: 6px; }}
  .stat {{ display: inline-block; margin-right: 2rem; }}
  .stat b {{ font-size: 1.6rem; display: block; }}
  .note {{ background: #fbf7e9; border-left: 4px solid #e0c060; padding: .6rem 1rem;
           border-radius: 4px; font-size: 14px; }}
</style></head><body>
<h1>GO-CAM curation cost estimates</h1>
<p class="sub">Derived from <code>geneontology/noctua-models</code> git history (last 2 years).</p>

<p>
  <span class="stat"><b>{n_models}</b> native GO-CAMs</span>
  <span class="stat"><b>{n_versions}</b> save events</span>
  <span class="stat"><b>~{total_hours}</b> person-hours (adjusted, lower bound)</span>
</p>

<p>The minerva→GitHub bot commits every ~5&nbsp;minutes, so each commit touching a
model is a <b>save event at ~5-min resolution</b>. Save events are grouped into
sessions; <b>active editing time</b> is measured as save-to-save spans within a
session — a lower bound that excludes literature reading and planning done outside
Noctua. <b>Edit size</b> is triples added/removed per save, from a DuckDB
triple-store-over-time.</p>

<h2>How long does a GO-CAM take to curate?</h2>
{summary_table}
<img src="curation_time.png" alt="distribution of curation time">

<h2>Edit-pattern gallery</h2>
<p>Representative models. Green = triples added, red = removed, line = total model size.</p>
<img src="gallery.png" alt="edit-pattern gallery">
<h3>Selected examples</h3>
{examples_table}

<p class="note"><b>Caveats.</b> True native GO-CAMs only (gene-centric/import models
excluded). Bulk pipeline commits dropped. Saves within one 5-min window collapse.
Active time is a lower bound on real effort.</p>
</body></html>
"""
