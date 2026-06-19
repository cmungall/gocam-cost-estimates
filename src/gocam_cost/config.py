"""Shared configuration and constants."""
from __future__ import annotations

import re
from pathlib import Path

REPO = "geneontology/noctua-models"
CLONE_URL = f"https://github.com/{REPO}"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}"

# Repo-root-relative locations (resolved against the package's repo, not cwd).
ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "vendor"
CLONE_DIR = VENDOR / "noctua-models"          # blobless shallow clone (timeline only)
BLOB_CACHE = VENDOR / "blobs"                  # cached raw .ttl, keyed by blob oid
DATA = ROOT / "data"
DUCKDB_PATH = DATA / "triples.duckdb"

# Analysis window: most recent 2 years.
WINDOW_START = "2024-06-19"
SHALLOW_SINCE = "2024-06-15"                   # small buffer before the window

# True native GO-CAMs have 16-hex-char ids; everything else (MGI_*, ZFIN_*,
# SGD_*, WB_*, SYNGO_*, YeastPathways_*, Reactome R-*) is gene-centric/imported.
NATIVE_ID = re.compile(r"^[0-9a-f]{16}$")

# A commit touching more than this many models is a pipeline/migration re-save.
BULK_THRESHOLD = 10

# Curation-time sessionization.
FINE_GAPS_MIN = [30, 60]     # wall-clock session gaps
DAY_GAPS = [1, 7, 30]        # calendar campaign gaps
SYNC_INTERVAL_MIN = 5        # minerva->github cron cadence (for adjusted estimate)

OWL = "http://www.w3.org/2002/07/owl#"
ANNOTATED_SOURCE = OWL + "annotatedSource"
ANNOTATED_PROPERTY = OWL + "annotatedProperty"
ANNOTATED_TARGET = OWL + "annotatedTarget"
