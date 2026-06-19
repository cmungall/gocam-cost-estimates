"""The canonical 'True GO-CAM' set, as defined by the GO production pipeline.

A True GO-CAM (gocam-py `pipeline/filter_true_gocam_models.py`) is a model that
is in `production` status, whose activity graph has >=1 causal edge with no
disconnected activity, and that has >=1 evidence assertion. The GO pipeline
publishes the filtered set as the go-cam-browser's bulk `data.json`; we treat
that as the authoritative model universe (and source of official per-model
structural stats) rather than reverse-engineering the filter ourselves.
"""
from __future__ import annotations

import httpx
import pandas as pd

from . import config as C

DATA_URL = "https://go-cam-browser.geneontology.org/data.json"
INDEX_PARQUET = C.DATA / "true_gocam_index.parquet"

_KEEP = {
    "id": "model_id",
    "title": "title",
    "status": "status",
    "taxon_label": "taxon",
    "number_of_activities": "n_activities",
    "length_of_longest_causal_association_path": "longest_path",
    "number_of_strongly_connected_components": "n_scc",
    "date_modified": "date_modified",
}


def fetch_index(force: bool = False) -> pd.DataFrame:
    """Return the canonical True GO-CAM index (cached as parquet)."""
    if INDEX_PARQUET.exists() and not force:
        return pd.read_parquet(INDEX_PARQUET)
    docs = httpx.get(DATA_URL, timeout=120).json()
    df = pd.DataFrame(docs)[list(_KEEP)].rename(columns=_KEEP)
    df["model_id"] = df["model_id"].str.replace(r"^gomodel:", "", regex=True)
    C.DATA.mkdir(parents=True, exist_ok=True)
    df.to_parquet(INDEX_PARQUET, index=False)
    return df


def true_gocam_ids() -> set[str]:
    return set(fetch_index()["model_id"])
