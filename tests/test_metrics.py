from datetime import datetime, timedelta

import pandas as pd
import pytest

from gocam_cost import metrics, patterns


def _dt(s):
    return datetime.fromisoformat(s)


@pytest.mark.parametrize("times,gap_min,expected_sessions,expected_active", [
    # two saves 25 min apart -> one 60m session, 25 min active
    (["2025-01-01T10:00", "2025-01-01T10:25"], 60, 1, 25.0),
    # same pair with a 20-min gap threshold -> two sessions, 0 active
    (["2025-01-01T10:00", "2025-01-01T10:25"], 20, 2, 0.0),
    # single save -> one session, 0 active
    (["2025-01-01T10:00"], 60, 1, 0.0),
])
def test_sessions(times, gap_min, expected_sessions, expected_active):
    ts = [_dt(t) for t in times]
    ss = metrics._sessions(ts, timedelta(minutes=gap_min))
    active = sum((e - s).total_seconds() for s, e in ss) / 60.0
    assert len(ss) == expected_sessions
    assert active == expected_active


def test_campaigns_gap():
    days = [_dt("2025-01-01T09:00"), _dt("2025-01-01T15:00"),  # same day
            _dt("2025-01-03T10:00"),                            # +2 days
            _dt("2025-02-01T10:00")]                            # ~month later
    assert metrics._campaigns(days, 1) == 3   # Jan1 | Jan3 | Feb1 (every gap > 1 day)
    assert metrics._campaigns(days, 7) == 2   # Jan1-Jan3 merge; Feb1 separate
    assert metrics._campaigns(days, 30) == 1  # all within 30-day gaps


def test_classify_patterns():
    df = pd.DataFrame([
        {"n_saves": 1, "sessions_60m": 1, "campaigns_7d": 1, "total_churn": 0},   # stub
        {"n_saves": 8, "sessions_60m": 1, "campaigns_7d": 1, "total_churn": 50},  # blitz
        {"n_saves": 6, "sessions_60m": 5, "campaigns_7d": 6, "total_churn": 40},  # slow_burn
        {"n_saves": 20, "sessions_60m": 4, "campaigns_7d": 3, "total_churn": 99}, # revisit_burst
    ])
    labels = patterns.classify(df).tolist()
    assert labels == ["stub", "blitz", "slow_burn", "revisit_burst"]
