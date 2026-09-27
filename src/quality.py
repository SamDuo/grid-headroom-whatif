"""Data-quality checks and alerts for the hourly demand panel.

    DATA_DIR=/path python src/quality.py

Runs five checks on the demand each utility submitted (raw), writes a per-grid summary, the
flagged hours, and alerts for anything over threshold, then builds a cleaned series and checks
it against EIA's own adjusted series.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("DATA_DIR", ROOT / "data"))
RESULTS = ROOT / "results"

SPIKE_DAYS = 3             # compare each hour with the same hour on the 3 days either side
SPIKE_REL = 0.35           # a raw value 35% away from that median is a spike
FORECAST_MAPE_ALERT = 0.05 # a day-ahead forecast off by more than 5% on average gets an alert


# ----------------------------------------------------------------------------- checks
def missing_hours(times: pd.Series) -> int:
    """Hours absent from an otherwise hourly series."""
    t = pd.DatetimeIndex(times).sort_values()
    expected = pd.date_range(t[0], t[-1], freq="h")
    return int(len(expected.difference(t)))


def spikes(values: pd.Series, days: int = SPIKE_DAYS, rel: float = SPIKE_REL) -> pd.Series:
    """True where a value sits more than `rel` away from the median of the same hour on nearby days.

    Comparing like hours keeps the normal daily cycle (afternoon peaks run 30-60% above the
    night) from being flagged; a rolling median across the day would flag every peak.
    """
    shifted = pd.concat([values.shift(24 * k) for k in range(-days, days + 1)], axis=1)
    med = shifted.median(axis=1, skipna=True)
    return (values - med).abs() > rel * med


def clean(raw: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Blank out missing, non-positive and spike hours, then interpolate across them in time."""
    bad = raw.isna() | (raw <= 0) | spikes(raw)
    cleaned = raw.mask(bad).interpolate(limit_direction="both")
    return cleaned, bad


def mape(actual: pd.Series, forecast: pd.Series) -> float:
    ok = actual.notna() & forecast.notna() & (actual > 0)
    return float(((forecast[ok] - actual[ok]).abs() / actual[ok]).mean())


# ----------------------------------------------------------------------------- run
def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    df = pd.read_parquet(DATA / "hourly.parquet").sort_values(["ba", "utc_hour_end"])
    summary, flags, alerts, cleaned_parts = [], [], [], []
    for ba, g in df.groupby("ba"):
        g = g.set_index("utc_hour_end")
        raw, adj = g.demand_raw, g.demand_adjusted
        spike = spikes(raw)
        cleaned, bad = clean(raw)
        agree = (cleaned - adj).abs() / adj
        eia_changed = ((raw - adj).abs() > 0.01 * adj) | (raw.isna() & adj.notna())
        row = {
            "ba": ba, "hours": len(g),
            "missing_hours": missing_hours(g.index.to_series()),
            "duplicate_hours": int((g.rows_for_this_hour > 1).sum()),
            "raw_null": int(raw.isna().sum()),
            "raw_non_positive": int((raw <= 0).sum()),
            "raw_spikes": int(spike.sum()),
            "hours_eia_changed": int(eia_changed.sum()),
            "hours_we_flagged": int(bad.sum()),
            # Scored against EIA's own corrections: of the hours EIA changed, how many did we flag,
            # and of the hours we flagged, how many did EIA also change?
            "recall_vs_eia": float((bad & eia_changed).sum() / max(eia_changed.sum(), 1)),
            "precision_vs_eia": float((bad & eia_changed).sum() / max(bad.sum(), 1)),
            "hours_eia_imputed": int(g.demand_imputed.notna().sum()),
            "raw_peak_mw": float(raw.max()),
            "cleaned_peak_mw": float(cleaned.max()),
            "eia_adjusted_peak_mw": float(adj.max()),
            "cleaned_within_1pct_of_eia": float((agree <= 0.01).mean()),
        }
        for year, gy in g.groupby(g.index.year):
            if len(gy) > 1000:                     # skip the few UTC hours that spill into the next year
                row[f"forecast_mape_{year}"] = mape(gy.demand_adjusted, gy.demand_forecast)
        summary.append(row)

        review = spike & ~eia_changed
        row["spike_days_for_review"] = int(pd.Series(g.index[review].date).nunique())
        hit = g[bad].assign(ba=ba, spike=spike[bad], cleaned=cleaned[bad])
        flags.append(hit.reset_index()[["ba", "utc_hour_end", "demand_raw", "cleaned", "demand_adjusted", "spike"]])
        # The what-if uses EIA's adjusted series; our cleaning only fills hours EIA left blank.
        # Spike flags are for review, not correction, because extreme weather is real demand.
        cleaned_parts.append(pd.DataFrame({"ba": ba, "utc_hour_end": g.index, "local_hour_end": g.local_hour_end.to_numpy(),
                                           "demand": adj.fillna(cleaned).to_numpy()}))

        if row["raw_peak_mw"] > 1.2 * row["eia_adjusted_peak_mw"]:
            alerts.append({"ba": ba, "severity": "high", "check": "peak",
                           "message": f"Raw peak {row['raw_peak_mw']:,.0f} MW is {row['raw_peak_mw'] / row['eia_adjusted_peak_mw']:.1f}x "
                                      f"the cleaned peak {row['eia_adjusted_peak_mw']:,.0f} MW; any capacity metric on raw data is wrong."})
        if row["raw_spikes"] > 0:
            alerts.append({"ba": ba, "severity": "review", "check": "raw_spikes",
                           "message": f"{row['raw_spikes']} hours look like spikes; {int(review.sum())} of them, on "
                                      f"{row['spike_days_for_review']} days, were left unchanged by EIA. Review before correcting: "
                                      "winter storms produce real spikes."})
        for check in ["missing_hours", "duplicate_hours", "raw_null", "raw_non_positive"]:
            if row[check] > 0:
                alerts.append({"ba": ba, "severity": "medium", "check": check, "message": f"{row[check]} hours failed {check}."})
        for year in sorted(g.index.year.unique()):
            m = row.get(f"forecast_mape_{year}")
            if m is not None and m > FORECAST_MAPE_ALERT:
                alerts.append({"ba": ba, "severity": "low", "check": "forecast_mape",
                               "message": f"{year} day-ahead forecast error {100 * m:.1f}% (threshold {100 * FORECAST_MAPE_ALERT:.0f}%)."})

    pd.DataFrame(summary).to_csv(RESULTS / "quality_summary.csv", index=False)
    pd.concat(flags).to_csv(RESULTS / "quality_flagged_hours.csv", index=False)
    (RESULTS / "alerts.json").write_text(json.dumps(alerts, indent=2))
    pd.concat(cleaned_parts).to_parquet(DATA / "demand_clean.parquet", index=False)
    print(pd.DataFrame(summary).T.to_string())
    print(json.dumps(alerts, indent=1))


if __name__ == "__main__":
    main()
