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

# Generate the static HTML report under docs/ (GitHub Pages)
docs:
    uv run gocam-cost docs

# Launch the marimo notebook
notebook:
    uv run marimo edit notebooks/cost_estimates.py

# Run tests
test:
    uv run pytest -q
