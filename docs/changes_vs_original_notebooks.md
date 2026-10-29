# What changed versus the original notebooks (and why)

A review of `flight_delay_analysis_cleaning_01.ipynb` and `flight_delay_visualization_02.ipynb` found the following
issues. All are fixed in the package.

| # | Original behaviour | Problem | Fix |
|---|---|---|---|
| 1 | Hard-coded relative CSV paths, intermediate CSV hand-offs between notebooks | Not reproducible; 1M-row CSVs re-parsed | Config-driven paths, Parquet output, one pipeline |
| 2 | Clock times converted to `datetime` on fake date `1900-01-01` | Meaningless date part; midnight crossings produce wrong dates | Minutes since midnight with modulo-1440 arithmetic; `2400` -> `0` |
| 3 | `cancellation_code` dropped ("more than 40 % null") | Nulls are *expected* (only cancelled flights have a code); lost the cancellation reason | Column kept and mapped to Carrier / Weather / NAS / Security |
| 4 | Cells executed out of order (`actual_dep_hour` used before it was created) | Notebook fails on "Restart & Run All" | Linear, tested pipeline |
| 5 | Flight number cast `float -> str` giving `"1234.0"` | Corrupt identifier | `float -> Int64 -> str` |
| 6 | Delay-cause averages computed over **all** flights | Cause columns are populated only when delay >= 15 min (zeros otherwise), so means are diluted by the large majority of on-time flights and cause magnitudes look far smaller than they are | Causes analysed among delayed flights, as share of delay minutes |
| 7 | Airport / route rankings with no minimum volume | A route with 2 flights and one 5-hour delay "wins" the worst-route ranking | Configurable minimum flights per group |
| 8 | No explicit "delayed" KPI flag; on-time share had to be inferred from status columns | Easy to mis-count cancelled/diverted flights as on time | Explicit `is_arr_delayed` (`<NA>` when not completed) and separate cancel / divert rates |
| 9 | Pie/donut for "average arrival delay by day type" | Averages are not parts of a whole | Grouped bars of rates |
| 10 | Airline map defined twice with different names; duplicate arrival-delay violin cell | Duplication, drift risk | Single lookup in config |
| 11 | Narrative insights hand-written in the README | Can drift from the data | `reports/insights.md` generated from computed tables |
| 12 | No tests, no logging, no validation | Silent failures | Schema validation, data-quality report, 26 unit/integration tests, structured logging |
| 13 | 64 MB visualisation notebook (outputs embedded) | Unusable in git | Outputs stripped in archive; charts rebuilt as standalone HTML |
| 14 | 115 `dep_time` and 538 `arr_time` values treated as missing and "imputed" | These are exactly the counts of `2400` (midnight) in the raw file; `%H%M` parsing rejects `2400`, creating artificial nulls | `2400` normalised to `0`; no imputation needed on this dataset (safeguard kept) |
| 15 | Outliers not addressed (only visible as stretched axes) | A 3,359-min delay can decide "worst route"; extreme delays are 0.34 % of flights but ~14 % of delay minutes | Explicit outlier policy: flag, quantify, winsorize rankings, never delete (`features/outliers.py`) |
