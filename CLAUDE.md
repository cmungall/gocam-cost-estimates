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
- `metrics.py` — sessions/campaigns + cohort summary (**True GO-CAMs only**).
- `patterns.py` — classify edit patterns; pick representatives (True GO-CAMs).
- `true_gocams.py` — fetch/cache the canonical True GO-CAM index (the
  go-cam-browser `data.json`) → `data/true_gocam_index.parquet`.
- `publish.py` — generate the self-contained interactive marimo notebook.
- `cli.py` — `gocam-cost {build,export,publish,docs,stats}`.

`notebooks/cost_estimates.py` — **generated** by `publish.py`; self-contained
(embeds production data as gzip+base64 CSV, inline plots, no `gocam_cost` import)
so `just docs` can export it to an interactive **WASM site** under `docs/` that
runs in-browser via Pyodide on GitHub Pages. Don't hand-edit it — edit the
template in `publish.py` and re-run `gocam-cost publish` / `just docs`.

## Key facts / gotchas

- **True GO-CAMs only**: model ids `^[0-9a-f]{16}$`. Gene-centric/import models
  (`MGI_*`, `ZFIN_*`, `SGD_*`, `WB_*`, `SYNGO_*`, `YeastPathways_*`, `R-*`) are excluded.
- **Canonical "True GO-CAM" set, not heuristics.** The GO production pipeline
  (`gocam-py` `pipeline/filter_true_gocam_models.py`) defines a True GO-CAM as a
  `production` model whose activities form a **connected causal graph** with
  evidence — a *causal-structure* test, NOT edit-count or id-regex. The filtered
  set (**2,099**) is published as the go-cam-browser bulk `data.json`; we fetch
  that as the authoritative universe (`true_gocams.py`) and flag `is_true_gocam`
  by membership. Don't reinvent the filter. (Earlier heuristics — hex16 ids,
  `production` state, ≥2 saves — were wrong both ways: they included ~1,989
  pseudo-GO-CAMs and excluded 151 non-hex True GO-CAMs like `YeastPathways_*`.)
- Curation **time** is only measurable for True GO-CAMs with ≥2 individual
  (non-bulk) saves in the window (~1,185 of the 2,099); the rest were touched
  only by bulk/import pipelines in-window or curated before it.
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
