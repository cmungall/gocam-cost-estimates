import marimo

__generated_with = "0.9.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    from pathlib import Path

    from gocam_cost import metrics, viz

    DATA = Path(__file__).resolve().parents[1] / "data"
    return DATA, Path, metrics, mo, pd, viz


@app.cell
def _(DATA, pd):
    curation = pd.read_parquet(DATA / "curation_metrics.parquet")
    versions = pd.read_parquet(DATA / "versions.parquet")
    examples = pd.read_parquet(DATA / "examples.parquet")
    return curation, examples, versions


@app.cell
def _(curation, mo):
    mo.md(
        f"""
        # GO-CAM curation cost estimates

        Built from `geneontology/noctua-models` git history. The minerva→GitHub
        bot commits every **~5 minutes**, so each commit touching a model is a
        **save event at ~5-min resolution**. We keep only **true native
        GO-CAMs** ({len(curation):,} models edited in the last 2 years), drop
        bulk pipeline commits, and group each model's save events into sessions.

        - **Active editing time** = save-to-save spans within a session (a lower
          bound; excludes literature reading / planning done outside Noctua).
        - **Edit size** = triples added / removed per save, from a DuckDB
          triple-store-over-time (OWL-axiom blank nodes skolemized).
        """
    )
    return


@app.cell
def _(curation, metrics, mo):
    summary = metrics.cohort_summary(curation)
    mo.md("## Headline cohorts")
    summary
    return (summary,)


@app.cell
def _(curation, mo):
    import matplotlib.pyplot as plt

    multi = curation[curation.n_saves >= 2]
    fig_h, ax_h = plt.subplots(figsize=(8, 3.2))
    ax_h.hist(multi.adj_min_60m.clip(upper=240), bins=40, color="#2a6f97")
    ax_h.set_xlabel("adjusted active editing time per model (min, 60-min gap, capped at 240)")
    ax_h.set_ylabel("models")
    ax_h.set_title(f"Distribution of curation time — multi-save models (n={len(multi):,})")
    fig_h.tight_layout()
    mo.md("## How long does an actively-curated model take?")
    fig_h
    return ax_h, fig_h, multi, plt


@app.cell
def _(examples, mo, versions, viz):
    mo.md(
        """
        ## Edit-pattern gallery (representative models)

        Green = triples added, red = removed, line = total model size.
        """
    )
    gallery = viz.plot_gallery(versions, examples)
    gallery
    return (gallery,)


if __name__ == "__main__":
    app.run()
