"""What-if model: how much new data-center load each grid can absorb, and what flexibility buys.

    DATA_DIR=/path python src/headroom.py        (after src/quality.py)

The test for each year: add a flat new load L to every hour. Wherever demand plus L would exceed
that year's peak (the most the system actually served), the new load must curtail by the excess.
The curtailment rate is curtailed energy over the new load's annual energy. A grid's "headroom at
0.5%" is the largest L whose curtailment rate stays at or below 0.5%. This is the screening method
used in recent load-flexibility studies; it ignores transmission limits, reserve margins and new
generation, so it screens, it does not plan.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("DATA_DIR", ROOT / "data"))
RESULTS, CHARTS = ROOT / "results", ROOT / "charts"

GRIDS = {"SOCO": "Southern Company (Georgia)", "ERCO": "ERCOT (Texas)", "PSCO": "Public Service Co. (Colorado)"}
RATES = [0.0025, 0.005, 0.01]
CAMPUS_MW = [250, 500, 1000, 2000]
YEARS = range(2021, 2026)


# ----------------------------------------------------------------------------- core
def curtailment(demand: np.ndarray, threshold: float, load: float) -> dict:
    """Curtailment a flat new load would need to keep demand at or below `threshold`."""
    excess = np.maximum(0.0, demand + load - threshold)
    on = excess > 0
    runs, longest = 0, 0
    for flag in on:                       # longest stretch of consecutive curtailed hours
        runs = runs + 1 if flag else 0
        longest = max(longest, runs)
    return {"rate": float(excess.sum() / (load * len(demand))) if load > 0 else 0.0,
            "hours": int(on.sum()), "longest_event_hours": longest,
            "mean_share_curtailed": float((excess[on] / load).mean()) if on.any() else 0.0}


def max_load(demand: np.ndarray, threshold: float, rate: float, tol: float = 1.0) -> float:
    """Largest flat load (MW) whose curtailment rate is at or below `rate`. The rate rises with
    load, so bisection works."""
    lo, hi = 0.0, float(threshold)
    while curtailment(demand, threshold, hi)["rate"] <= rate:
        hi *= 2
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if curtailment(demand, threshold, mid)["rate"] <= rate:
            lo = mid
        else:
            hi = mid
    return lo


# ----------------------------------------------------------------------------- run
def main() -> None:
    CHARTS.mkdir(exist_ok=True)
    df = pd.read_parquet(DATA / "demand_clean.parquet")
    df["year"] = pd.DatetimeIndex(df.local_hour_end).year
    df = df[df.year.isin(YEARS)]

    kpi, headroom, scenarios = [], [], []
    for ba, g in df.groupby("ba"):
        for year, gy in g.groupby("year"):
            d = gy.demand.to_numpy()
            peak = float(d.max())
            kpi.append({"ba": ba, "year": year, "peak_mw": peak, "average_mw": float(d.mean()),
                        "load_factor": float(d.mean() / peak)})
            month = pd.DatetimeIndex(gy.local_hour_end).month.to_numpy()
            for r in RATES:
                L = max_load(d, peak, r)
                c = curtailment(d, peak, L)
                on = d + L > peak
                headroom.append({"ba": ba, "year": year, "rate": r, "load_mw": L, "share_of_peak": L / peak,
                                 "hours_curtailed": c["hours"], "longest_event_hours": c["longest_event_hours"],
                                 "mean_share_curtailed": c["mean_share_curtailed"],
                                 # when the curtailment falls: summer (Jun-Sep) vs winter (Dec-Feb)
                                 "summer_hours": int((on & np.isin(month, [6, 7, 8, 9])).sum()),
                                 "winter_hours": int((on & np.isin(month, [12, 1, 2])).sum())})
            for mw in CAMPUS_MW:
                c = curtailment(d, peak, mw)
                scenarios.append({"ba": ba, "year": year, "campus_mw": mw, **c})

    kpi = pd.DataFrame(kpi)
    kpi["peak_growth"] = kpi.groupby("ba").peak_mw.pct_change()
    headroom, scenarios = pd.DataFrame(headroom), pd.DataFrame(scenarios)
    head = headroom.groupby(["ba", "rate"]).agg(
        load_mw_mean=("load_mw", "mean"), load_mw_worst_year=("load_mw", "min"),
        share_of_peak=("share_of_peak", "mean"), hours_curtailed=("hours_curtailed", "mean"),
        longest_event_hours=("longest_event_hours", "max"), mean_share_curtailed=("mean_share_curtailed", "mean"),
        summer_hours=("summer_hours", "mean"), winter_hours=("winter_hours", "mean")).reset_index()
    scen = scenarios.groupby(["ba", "campus_mw"]).agg(
        rate=("rate", "mean"), rate_worst_year=("rate", "max"), hours=("hours", "mean"),
        longest_event_hours=("longest_event_hours", "max")).reset_index()

    kpi.to_csv(RESULTS / "kpi_by_year.csv", index=False)
    headroom.to_csv(RESULTS / "headroom_by_year.csv", index=False)
    head.to_csv(RESULTS / "headroom_summary.csv", index=False)
    scen.to_csv(RESULTS / "campus_scenarios.csv", index=False)
    charts(head, scen)
    print(kpi.round(3).to_string(index=False))
    print(head.round(3).to_string(index=False))
    print(scen.round(4).to_string(index=False))


# ----------------------------------------------------------------------------- charts
INK, MUTED, LINE = "#1f262b", "#65767f", "#d5dde2"
COLORS = {"SOCO": "#1c5c84", "ERCO": "#c05a2b", "PSCO": "#6f8688"}


def tidy(ax, title):
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=10)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(LINE)
    ax.tick_params(colors=MUTED)


def charts(head: pd.DataFrame, scen: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    width = 0.26
    for i, ba in enumerate(GRIDS):
        h = head[head.ba == ba]
        x = np.arange(len(RATES)) + (i - 1) * width
        ax.bar(x, h.load_mw_mean / 1000, width, color=COLORS[ba], label=GRIDS[ba])
        for xi, v in zip(x, h.load_mw_mean / 1000):
            ax.text(xi, v + 0.2, f"{v:.1f}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(range(len(RATES)), [f"{100 * r:g}%" for r in RATES])
    ax.set_xlabel("Curtailment allowed (share of the new load's annual energy)", color=MUTED)
    ax.set_ylabel("New flat load absorbed (GW)", color=MUTED)
    tidy(ax, "New load each grid can take without a new peak, by how flexible that load is")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(CHARTS / "headroom_by_flexibility.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    for ba in GRIDS:
        s = scen[scen.ba == ba]
        ax.plot(s.campus_mw, s.hours, marker="o", lw=2, color=COLORS[ba], label=GRIDS[ba])
    ax.set_xlabel("New data-center campus (MW, flat load)", color=MUTED)
    ax.set_ylabel("Hours a year it must curtail", color=MUTED)
    ax.set_xticks(CAMPUS_MW)
    tidy(ax, "How often a campus would have to flex so the grid never sets a new peak")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(CHARTS / "campus_curtailment_hours.png", dpi=180); plt.close(fig)


if __name__ == "__main__":
    main()
