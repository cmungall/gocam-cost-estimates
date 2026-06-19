# GO-CAM cost estimates

# Full data build: clone timeline, fetch contents, extract, build DuckDB, export
build:
    uv run gocam-cost build

# Re-export the small committed artifacts from an existing DuckDB
export:
    uv run gocam-cost export

# Print headline cohort summary
stats:
    uv run gocam-cost stats

# Re-clone the source repo from scratch
refresh:
    rm -rf vendor/noctua-models
    uv run gocam-cost build

# Regenerate the self-contained interactive notebook (embeds production data)
publish:
    uv run gocam-cost publish

# Publish the interactive notebook to docs/ as a WASM site (GitHub Pages)
docs:
    uv run gocam-cost docs

# Edit/run the interactive marimo notebook locally
notebook:
    uv run marimo edit notebooks/cost_estimates.py

# Run tests
test:
    uv run pytest -q
