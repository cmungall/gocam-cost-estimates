# gocam-cost-estimates

Estimate how much **curation effort** goes into [GO-CAM](https://geneontology.org/docs/gocam-overview/)
models, from the public `geneontology/noctua-models` git history — backed by a
reusable **DuckDB triple-store-over-time**.

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
just stats      # headline cohort summary
just notebook   # marimo: curation-time summary + edit-pattern gallery
```

The big clone (`vendor/`) and full `data/triples.duckdb` are gitignored and
rebuildable; small derived parquet under `data/` is committed so the notebook
runs out of the box.
