# GO-CAM Cost Estimates — Design Spec

Estimate how much **curation effort** goes into GO-CAM models, from the public
`geneontology/noctua-models` git history, and expose the underlying data as a
reusable **DuckDB triple-store-over-time**.

## Background / data facts (validated)

- Every model is a file `models/<id>.ttl` in `geneontology/noctua-models`.
- A bot syncs minerva → GitHub with an **`automated commit` every ~5 minutes**.
  So each commit touching a model is a **save event at ~5-min resolution** —
  far finer than the internal `dc:date` annotations (which are day-granular).
- The `.ttl` is **expanded long-form Turtle** (full IRIs, one statement per
  line). pyoxigraph parses a real ~550-triple model in **~0.6 ms**.
- The only blank nodes are **OWL axiom reifications** (evidence/provenance on an
  edge): `_:b owl:annotatedSource/Property/Target …; lego:evidence …; dc:date …;
  dc:contributor …`. They are **deterministically skolemizable** from
  `(annotatedSource, annotatedProperty, annotatedTarget)`.

## Scope decisions

- **True GO-CAMs only**: model ids matching `^[0-9a-f]{16}$` (native Noctua).
  Excludes gene-centric / pipeline models (`MGI_*`, `ZFIN_*`, `SGD_*`, `WB_*`,
  `SYNGO_*`, `YeastPathways_*`, Reactome `R-*`).
- **Window**: last 2 years (commits since **2024-06-19**).
- **Bulk commits dropped**: a commit touching > 10 models is a pipeline/migration
  re-save, not curation (49–100 such commits, one re-saving all 54,598 models).
- **Production state only** for *reported* cohorts: `lego:modelstate` is read
  from the latest version's triples; deleted/development/internal_test/review/
  template models are excluded (~3,325 production vs ~4,515 any-state edited
  in-window; production + ≥2 saves ≈ 2,100, matching go-cam-browser).
- **Triple DB scope**: in-window native cohort — ~4,515 models, ~25,833 versions
  (the triple store keeps all states; the production filter is applied at report time).
- **Storage**: snapshot-per-version (every triple of every version); diffs and
  counts derived in SQL.

## Pipeline (Python orchestrates; Rust + DuckDB do the heavy lifting)

1. **acquire** — blobless `--shallow-since` clone (≈114 MB) for the timeline;
   parse `git log --raw --no-abbrev` → `versions(model_id, sha, commit_time,
   blob_oid, fan_out)`, filtered to native + non-bulk.
2. **fetch blobs** — bulk-fetch exactly the needed blob OIDs into the local clone
   (batched `git fetch`), so extraction is fully local.
3. **extract** — `git cat-file --batch` streams blobs; **pyoxigraph (Rust)**
   parses each version (~16 s for the whole cohort). Emit raw triples (bnode
   labels kept, unique per version).
4. **load + transform in DuckDB**:
   - **Skolemize in SQL**: pivot axiom bnodes on annotatedSource/Property/Target,
     `md5` → `urn:skolem:axiom:<hash>`; rewrite subjects.
   - **Diff in SQL**: per-model version ordinal; `triples_added/removed` via key
     join against the previous version.
   - **Counts** per version.
   No per-triple work happens in Python.

## DuckDB schema

```
models(model_id, title, group, contributors, first_seen, last_seen, n_versions)
versions(version_id, model_id, sha, commit_time, n_triples, triples_added, triples_removed, fan_out)
triples(version_id, model_id, commit_time, subject, predicate, object, obj_is_literal)
```

## Curation-time metric (git timestamps; independent of triples)

Per model, group save events into **sessions** (wall-clock gap) and **campaigns**
(calendar-day gap):
- sessions at 30 / 60 min gaps → measured active editing time (lower bound);
  adjusted = measured + one 5-min sync interval per session.
- campaigns at 1 / 7 / 30 day gaps → calendar spread.
Cohorts (production only): all production; ≥2 saves (real curation); ≥5 saves
(substantial).

## Notebook & docs (interactive WASM, `notebooks/cost_estimates.py`)

`publish.py` generates a **self-contained** marimo notebook (production data
embedded as gzip+base64 CSV, inline plots, no `gocam_cost` import). `just docs`
exports it to an interactive **WASM site** under `docs/` (runs in-browser via
Pyodide on GitHub Pages). Contents:
- **Curation-time summary**: cohort medians/means + distribution.
- **Interactive explorer**: a filterable model table (search / min-saves / pattern);
  clicking a row renders that model's edit timeline (x = commit time, green =
  triples added, red = removed, line = total size).

## Reproducibility

Committed (small): `data/curation_metrics.parquet`, `data/versions.parquet`, and
the generated `notebooks/cost_estimates.py` + `docs/`. Gitignored (rebuildable):
`vendor/` clone, `data/triples.duckdb`. `just build` rebuilds; `just refresh`
re-clones; `just docs` re-publishes the site.

## Out of scope (YAGNI)

Full-population overview raster; per-curator dashboards; live barista access;
dollar-cost modeling.
