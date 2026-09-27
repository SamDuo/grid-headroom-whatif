# Decision memo: siting flexible data-center load in Georgia, Texas and Colorado

**To:** Infrastructure strategy and operations (portfolio exercise on public EIA data)
**From:** Sam Duong
**Decision needed:** Where can the next large campus go without forcing new peak capacity, and how
much flexibility should we commit to?

## Recommendation

1. **Commit to about 0.5% curtailment in interconnection talks.** It unlocks roughly 5.0 GW in
   Georgia, 3.8 GW in Texas and 1.3 GW in Colorado of new flat load that never sets a new system peak.
2. **Put gigawatt-scale campuses in Georgia or Texas before Colorado.** A 1 GW campus needs about
   10 to 13 hours of flex a year there, against 77 in Colorado. At 2 GW, Colorado rises to 345 hours.
3. **Plan Georgia flex for long winter events.** Curtailment is mostly summer afternoons, but
   Georgia's longest event was 15 hours during Winter Storm Elliott. Workload shifting or storage
   for Georgia sites should be sized for that, not for a 3-hour summer peak.

## Why

- Five years of hourly demand (131,472 hours) for the three grids. The test is whether new load
  would push demand past the peak each system already served.
- Answers vary by year. The worst year at 0.5% still leaves 4.2 GW (Georgia), 3.0 GW (Texas) and
  1.0 GW (Colorado), so the recommendation holds in a bad year.

## Before anyone uses these numbers

- **The raw utility data would have doubled two grids' peaks** (Georgia 92 GW instead of 48 GW,
  Colorado 19 GW instead of 10 GW). Our checks flag this automatically. Use the adjusted series.
- **Colorado's day-ahead forecast feed has been unreliable since 2023** (error 46.7% in 2023, above 5%
  since). Raise it with the data owner before building anything on that forecast.
- **This is a screen.** Transmission and substation limits decide individual sites. The next step
  is a site-level study with the utility for the top candidate locations.
