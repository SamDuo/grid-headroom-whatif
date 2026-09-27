"""Load five years of EIA-930 hourly demand for SOCO, ERCO and PSCO into one Parquet panel.

    DATA_DIR=/path python src/build.py
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("DATA_DIR", ROOT / "data"))


def main() -> None:
    t0 = time.time()
    sql = (ROOT / "sql" / "01_hourly_demand.sql").read_text().format(files=str(DATA / "EIA930_BALANCE_*.csv"))
    con = duckdb.connect()
    df = con.sql(sql).df()
    df.to_parquet(DATA / "hourly.parquet", index=False)
    by_ba = df.groupby("ba").size().to_dict()
    print(f"{len(df):,} hourly rows {by_ba} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
