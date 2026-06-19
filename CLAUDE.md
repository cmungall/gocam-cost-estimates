# gocam-cost-estimates

Estimate **GO-CAM curation effort** from `geneontology/noctua-models` git history,
backed by a reusable **DuckDB triple-store-over-time**. See `SPEC.md` for the full
design and `README.md` for quick-start.

## What this is

The minerva→GitHub bot commits every **~5 minutes**, so each commit touching
`models/<id>.ttl` is a **save event at ~5-min resolution**. From this we derive:

- **curation time** — save events grouped into sessions (wall-clock gaps) and
  campaigns (calendar gaps); active editing time is a *lower bound*.
- **edit size** — triples added/removed per save, from every version's triples
  loaded into DuckDB.

## Architecture (Python orchestrates; Rust + DuckDB do the heavy lifting)

`src/gocam_cost/`
- `config.py` — paths, window (`2024-06-19`), native-id regex, bulk threshold.
- `gitdata.py` — blobless `--shallow-since` clone; `enumerate_versions()` parses
  `git log --raw --no-abbrev` → native, non-bulk versions (skips deletions).
- `fetch.py` — async HTTP fetch of each version's `.ttl` from `raw.githubusercontent.com`,
  cached on disk by blob oid (~1.4 min for the full cohort).
- `extract.py` — pyoxigraph (Rust) parses each version → raw-triple Parquet.
- `db.py` — DuckDB: **skolemize** OWL-axiom blank nodes and **diff** consecutive
  versions, all in SQL (never per-triple Python loops).
- `metrics.py` — sessions/campaigns + cohort summary.
- `patterns.py` — classify edit patterns, pick gallery representatives.
- `viz.py` — `plot_gallery()` (matplotlib) for the examples-only gallery.
- `cli.py` — `gocam-cost {build,export,stats}`.

`notebooks/cost_estimates.py` — marimo report.

## Key facts / gotchas

- **True GO-CAMs only**: model ids `^[0-9a-f]{16}$`. Gene-centric/import models
  (`MGI_*`, `ZFIN_*`, `SGD_*`, `WB_*`, `SYNGO_*`, `YeastPathways_*`, `R-*`) are excluded.
- **Bulk commits dropped**: a commit touching > 10 models is a pipeline re-save
  (some re-save all 54,598 models); these are not curation.
- **Resolution floor**: saves within one 5-min window collapse into one commit.
- **Skolemization**: axiom blank nodes get `urn:skolem:axiom:<md5(src+prop+tgt)>`,
  giving stable identity across versions so a date change reads as 1 add + 1 remove.
- Internal `dc:date` annotations are **day-granular**; we deliberately use git
  commit times instead (~5-min).

## Data handling

- Committed (small): `data/curation_metrics.parquet`, `data/versions.parquet`,
  `data/examples.parquet`, `data/example_triples.parquet`.
- Gitignored (rebuildable): `vendor/` (clone + blob cache + raw parquet),
  `data/triples.duckdb` (the full triple store).
- `just build` rebuilds everything; `just export` re-writes the committed parquet
  from an existing DuckDB; `just stats` prints the cohort summary.

## Working conventions

- Python via **uv**; tasks via **just**; CLI via **typer** (no argparse).
- Tests are **pytest** (`just test`). Avoid try/except as control flow — let
  unexpected errors surface.
- The heavy clone/DB live under `vendor/` and `data/triples.duckdb`; do not commit them.
- Network access (the HTTP fetch) only works in the **foreground** here; the
  extract/DB steps need no network.
