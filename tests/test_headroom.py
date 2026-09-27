"""The what-if math and the quality checks behave as specified on cases small enough to check by hand."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from headroom import curtailment, max_load  # noqa: E402
from quality import clean, mape, missing_hours, spikes  # noqa: E402


def test_curtailment_zero_when_load_fits_under_the_peak():
    demand = np.array([80.0, 90.0, 100.0, 70.0])
    assert curtailment(demand, 100.0, 0.0)["rate"] == 0.0
    c = curtailment(demand, 100.0, 10.0)          # only the peak hour spills over, by 10
    assert c["hours"] == 1
    assert c["rate"] == pytest.approx(10 / (10 * 4))


def test_curtailment_counts_the_longest_consecutive_event():
    demand = np.array([100, 100, 50, 100, 100, 100, 50], float)
    assert curtailment(demand, 100.0, 5.0)["longest_event_hours"] == 3


def test_max_load_hits_the_rate_budget():
    rng = np.random.default_rng(0)
    demand = 1000 + 300 * np.sin(np.arange(8760) / 24 * 2 * np.pi) + rng.normal(0, 20, 8760)
    peak = demand.max()
    L = max_load(demand, peak, 0.005)
    assert curtailment(demand, peak, L)["rate"] <= 0.005
    assert curtailment(demand, peak, L + 5)["rate"] > 0.005   # a little more load breaks the budget


def test_max_load_rises_with_flexibility():
    rng = np.random.default_rng(1)
    demand = rng.gamma(20, 50, 8760)
    peak = demand.max()
    assert max_load(demand, peak, 0.0025) < max_load(demand, peak, 0.005) < max_load(demand, peak, 0.01)


def test_spike_check_flags_a_planted_spike_but_not_the_daily_cycle():
    hours = pd.date_range("2024-06-01", periods=24 * 14, freq="h")
    daily = 1000 + 500 * np.sin((hours.hour - 9) / 24 * 2 * np.pi)     # a big, normal daily swing
    values = pd.Series(daily, index=hours)
    values.iloc[200] *= 2.0                                               # one bad hour
    flagged = spikes(values)
    assert flagged.iloc[200]
    assert flagged.sum() == 1


def test_clean_fills_bad_hours_by_interpolation():
    s = pd.Series([100.0, np.nan, 102.0, -5.0, 104.0])
    cleaned, bad = clean(s)
    assert bad.tolist() == [False, True, False, True, False]
    assert cleaned.tolist() == pytest.approx([100.0, 101.0, 102.0, 103.0, 104.0])


def test_missing_hours_and_mape():
    t = pd.Series(pd.date_range("2024-01-01", periods=10, freq="h").delete([3, 7]))
    assert missing_hours(t) == 2
    assert mape(pd.Series([100.0, 200.0]), pd.Series([110.0, 180.0])) == pytest.approx(0.10)
