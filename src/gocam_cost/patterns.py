"""Classify each model's edit pattern and pick representative examples.

Patterns (heuristic, from save-event timing + size):
  - stub          : a single save event
  - blitz         : all activity within one wall-clock session (~one sitting)
  - revisit_burst : a few distinct sessions/campaigns, each a burst of edits
  - slow_burn     : edits spread thinly across many calendar days/weeks
"""
from __future__ import annotations

import pandas as pd


def classify(df: pd.DataFrame) -> pd.Series:
    def label(r) -> str:
        if r.n_saves <= 1:
            return "stub"
        if r.sessions_60m <= 1:
            return "blitz"
        if r.campaigns_7d >= 4 and r.n_saves / max(r.campaigns_7d, 1) < 3:
            return "slow_burn"
        return "revisit_burst"
    return df.apply(label, axis=1)


def representatives(df: pd.DataFrame, per_pattern: int = 2) -> pd.DataFrame:
    """Pick a couple of clear, substantial exemplars per pattern for the gallery.

    Canonical True GO-CAMs only.
    """
    d = df[df.is_true_gocam].copy()
    d["pattern"] = classify(d)
    picks = []
    for pat, g in d.groupby("pattern"):
        # prefer models with enough substance to be illustrative
        g = g.sort_values(["total_churn", "n_saves"], ascending=False)
        if pat == "stub":
            g = g.sort_values("max_triples", ascending=False)
        picks.append(g.head(per_pattern))
    return pd.concat(picks).reset_index(drop=True)
