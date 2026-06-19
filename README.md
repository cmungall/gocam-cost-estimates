# gocam-cost-estimates

Estimate how much **curation effort** goes into [GO-CAM](https://geneontology.org/docs/gocam-overview/)
models, from the public `geneontology/noctua-models` git history — backed by a
reusable **DuckDB triple-store-over-time**.

📊 **Report (GitHub Pages):** https://cmungall.github.io/gocam-cost-estimates/

See [SPEC.md](SPEC.md) for the design and validated data facts.

## How it works

The minerva→GitHub bot commits every ~5 minutes, so each commit touching
`models/<id>.ttl` is a **save event at ~5-min resolution**. We:

1. clone the timeline (blobless, shallow),
2. fetch each true-GO-CAM version's `.ttl` over HTTP,
3. parse with pyoxigraph (Rust) and load every version's triples into DuckDB,
4. **skolemize** OWL-axiom blank nodes and **diff** consecutive versions in SQL,
5. derive curation-time sessions and per-save edit sizes (triples added/removed).

## Quick start

```bash
uv sync
just build      # full data build (clone + fetch + extract + DuckDB + export)
just stats      # headline cohort summary (production models only)
just notebook   # edit/run the interactive notebook locally
just docs       # publish the interactive WASM site to docs/
```

The big clone (`vendor/`) and full `data/triples.duckdb` are gitignored and
rebuildable; small derived parquet under `data/`, the generated notebook, and
`docs/` are committed so the site works out of the box.

## Scope

The model universe is the canonical **True GO-CAM** set (**2,099**) as defined by
the GO production pipeline ([gocam-py](https://github.com/geneontology/gocam-py)
`filter_true_gocam_models`: production status + connected causal activity graph +
evidence) and published as the [go-cam-browser](https://go-cam-browser.geneontology.org/)
`data.json`. Curation **time** is measured for the ~1,185 True GO-CAMs with ≥2
individual (non-bulk) saves in the last 2 years.
