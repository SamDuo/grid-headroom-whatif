#!/usr/bin/env bash
# Download EIA-930 six-month BALANCE files for 2021-2025 (about 430 MB) into $DATA_DIR.
set -euo pipefail
DATA_DIR="${DATA_DIR:-data}"; mkdir -p "$DATA_DIR"
for y in 2021 2022 2023 2024 2025; do
  for h in Jan_Jun Jul_Dec; do
    f="EIA930_BALANCE_${y}_${h}.csv"
    [ -s "$DATA_DIR/$f" ] || curl -sSf -o "$DATA_DIR/$f" "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/$f"
    echo "ok $f"
  done
done
