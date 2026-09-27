-- Hourly demand for the three balancing authorities that serve the posting's locations:
--   SOCO  Southern Company (Georgia and Alabama; Atlanta)
--   ERCO  ERCOT (most of Texas; Austin, Addison)
--   PSCO  Public Service Company of Colorado (Denver metro; Thornton)
--
-- EIA-930 reports three versions of demand: the value the utility submitted (raw), a flag for
-- hours EIA filled in (imputed), and EIA's cleaned series (adjusted). All three are kept so the
-- quality checks can compare them. Numbers arrive as text with thousands separators.
--
-- Input: {files} (EIA930_BALANCE_*.csv six-month files).

WITH raw AS (
    SELECT *
    FROM read_csv('{files}', header = true, all_varchar = true, union_by_name = true)
    WHERE "Balancing Authority" IN ('SOCO', 'ERCO', 'PSCO')
),
typed AS (
    SELECT
        "Balancing Authority"                                                          AS ba,
        strptime("UTC Time at End of Hour", '%m/%d/%Y %I:%M:%S %p')                    AS utc_hour_end,
        strptime("Local Time at End of Hour", '%m/%d/%Y %I:%M:%S %p')                  AS local_hour_end,
        TRY_CAST(replace("Demand (MW)", ',', '') AS DOUBLE)                            AS demand_raw,
        TRY_CAST(replace("Demand (MW) (Imputed)", ',', '') AS DOUBLE)                  AS demand_imputed,
        TRY_CAST(replace("Demand (MW) (Adjusted)", ',', '') AS DOUBLE)                 AS demand_adjusted,
        TRY_CAST(replace("Demand Forecast (MW)", ',', '') AS DOUBLE)                   AS demand_forecast
    FROM raw
)
SELECT ba, utc_hour_end, local_hour_end, demand_raw, demand_imputed, demand_adjusted, demand_forecast,
       count(*) OVER (PARTITION BY ba, utc_hour_end) AS rows_for_this_hour   -- duplicates show up here
FROM typed
ORDER BY ba, utc_hour_end;
