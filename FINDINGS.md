# Airline Delay Intelligence - Key Findings, Analysis, Limitations and Roadmap

> **Data:** 1,000,000 flights randomly sampled from ~7 million US domestic flights in 2024 (BTS on-time data).
> **Every number below was computed by the pipeline in this repo from your file** (`make run`) and can be reproduced from
> `reports/tables/*.csv` and `reports/insights.md`. A flight is **delayed** when it arrives **≥ 15 minutes** late (US DOT standard);
> cancelled and diverted flights are reported separately and never counted as "on time".

---

## 1. Business problem (one paragraph)

Late and cancelled flights cost airlines aircraft hours, crew time, passenger compensation and loyalty.
Operations, schedule-planning and station teams need to know **where, when and why** disruption happens - and which causes are
**controllable**. This project answers that with five questions: how reliable is the network, what causes delay minutes,
who/where are the weak spots, when does disruption concentrate, and why do flights get cancelled.
(Full framing, stakeholders and KPIs: `docs/business_problem.md`.)

---

## 2. Headline numbers

| KPI | Value |
|---|---|
| Flights analysed | 1,000,000 (984,033 completed · 13,608 cancelled · 2,359 diverted) |
| On-time arrival (< 15 min late) | **79.15 %** (delay rate 20.85 %) |
| Cancellation / diversion rate | **1.36 %** / 0.24 % |
| Median arrival delay | **-6 min** (the typical flight arrives early) |
| Mean arrival delay | 7.11 min raw · 5.90 min winsorized |
| 90th-percentile arrival delay | 43 min |
| Average lateness of a delayed flight | 71.5 min |

**Why the median and the mean disagree:** a typical flight is early, but a long tail of very late flights pulls the mean up.
Averages alone would mislead, so the project reports median, P90 and winsorized means next to raw means.

---

## 3. Key findings

### Finding 1 - Delay is mostly a *knock-on* and *airline-side* problem, not a weather problem
| Cause | Share of delay minutes |
|---|---|
| Late aircraft (previous flight arrived late) | **40.2 %** |
| Carrier (crew, maintenance, ground handling, gate) | **34.5 %** |
| NAS (air-traffic / airport system) | 19.1 % |
| Weather | **6.1 %** |
| Security | 0.2 % |

Roughly **three quarters (74.6 %)** of delay minutes come from carrier-side and late-aircraft causes - the part an airline can
influence with scheduling, turnaround buffers and operational readiness. Weather is small for delays (but see Finding 6).

### Finding 2 - Delays snowball through the day (cascade effect)
* Average departure delay (winsorized) rises from **2.8 min at 06:00 to 19.6 min at 20:00**.
* Delay rate rises from **9.6 % to 30.8 %** over the same hours.
* The late-aircraft share of delay minutes climbs from **13.7 % (06:00) to 49.7 % (20:00)** - direct evidence that early
  disruptions propagate down each aircraft's rotation.
* Departing early morning is by far the most reliable choice for passengers; evening banks are the highest-risk windows
  for operations teams to buffer.

### Finding 3 - A late departure almost always becomes a late arrival; little time is recovered
* **80.5 %** of flights leaving ≥ 15 min late also arrive ≥ 15 min late; only 5.4 % of on-time departures arrive late.
* Late departures recover just **4.5 min** on average in the air (long haul 7.9 · medium 4.6 · short 2.9 min).
  Short hops have almost no room to catch up.
* **20.4 %** of late arrivals left on time - delay created *en route* (NAS/airspace, taxi-in, holding) is a distinct problem.
* Correlation: departure delay vs arrival delay = **0.97**; carrier delay 0.68 and late-aircraft delay 0.62 relate to arrival
  delay far more than weather (0.31). Distance has ~0 correlation with delay (haul-length delay rates are similar, 19.6-21.5 %).

### Finding 4 - Outliers are rare but carry a heavy share of the damage
| Delay severity (delayed flights only) | % of delayed flights | % of delay minutes |
|---|---|---|
| 15-59 min | 64.7 % | 28.0 % |
| 60-179 min | 28.3 % | 39.5 % |
| 180-359 min | 5.3 % | 17.8 % |
| **360+ min (extreme)** | **1.6 %** | **14.8 %** |

* 3,332 flights (0.34 % of completed flights) were ≥ 6 h late and account for **13.8 % of all positive delay minutes**;
  **74 flights were more than 24 h late** (maximum 3,359 min ≈ 56 h).
* These are real events (overnight cancellations re-flown next day, aircraft swaps), so **nothing was deleted**; they are flagged
  (`is_extreme_delay`) and **rankings use winsorized means** so a handful of multi-day delays cannot decide who is "worst".
* Extreme-delay *rate* differs sharply by airline: American 0.74 % of flights, Frontier 0.61 %, Delta 0.33 % versus **Southwest 0.04 %**.

### Finding 5 - Cancellations are event-driven, not a steady drip
* The **10 worst days hold 23.3 % of all cancellations** (10 of 366 days). Without them the cancellation rate falls from 1.36 % to 1.07 %.
* **19 Jul 2024:** 17.3 % of flights cancelled and 57.6 % delayed; **91 % of that day's cancellations are coded "Carrier"** and one
  airline (Delta) accounts for 207 of 534 cancelled flights in the sample - consistent with a carrier-side systems failure
  (the widely reported July 2024 IT outage is a plausible explanation, **but the dataset cannot confirm the cause**).
* **15-16 Jan 2024:** 13-16 % cancelled, 78-81 % coded Weather (winter storm pattern).
* Monthly averages therefore hide the real story: January (3.62 %) and July (2.91 %) look bad mainly because of a few extreme days.

### Finding 6 - Why flights get cancelled
Weather **55.6 %**, Carrier **32.6 %**, NAS **11.9 %**, Security 0 % (no code D in this sample).
Weather matters far more for cancellations than for delays: it is a small *delay* driver but the leading *cancellation* driver.

### Finding 7 - Strong seasonality and a Friday/Sunday pattern
* **Delay rate by month:** worst **July 29.5 %**, May 26.6 %, June 25.0 %; best **October 13.3 %**, November 14.6 %, September 15.4 %.
  Summer peaks combine thunderstorms, high demand and the July 19 event.
* **Day of week:** Friday (23.3 %) and Sunday (22.7 %) are worst; Tuesday (18.0 %) and Wednesday (18.6 %) best.
  "Weekend vs weekday" is only a small gap (21.6 % vs 20.6 %) - the real pattern is Friday/Sunday travel peaks.

### Finding 8 - Airline reliability differs, and the *type* of problem differs by airline
| | Delay rate | Cancel rate |
|---|---|---|
| Best: Republic Airways / Hawaiian / Endeavor / Delta | 14.2 % / 15.1 % / 15.9 % / 17.3 % | - |
| Worst: Frontier / American / JetBlue / Spirit | 28.7 % / 26.2 % / 25.6 % / 23.7 % | - |
| Highest cancel rate | Frontier 2.39 %, Endeavor 2.32 % | Lowest: Southwest 0.80 %, Delta 0.95 % |

* 95 % confidence margins on airline delay rates are only ±0.2-0.7 pp, so the gap between the best and worst groups is real,
  but neighbouring airlines (e.g. Allegiant 21.8 %, PSA 21.7 %, Alaska 22.0 %) are statistically indistinguishable.
* Cause mix reveals different fixes: **Hawaiian** 59 % carrier-caused; **Spirit** 43 % NAS-caused (airspace/airports);
  **Frontier, Southwest, PSA, American** 48-54 % late-aircraft (rotation knock-on); **SkyWest** 15.6 % weather (regional/mountain network).

### Finding 9 - Airports and routes: busy hubs are not automatically the problem
* Delay rate by large hub: **MIA 28.1 %, CLT 27.4 %, DFW 27.1 %** vs **ATL 20.0 %, PHX 19.4 %, LAX 18.4 %, LGA 18.0 %**.
  Highest winsorized departure delay among sizeable airports: **MIA 18.0 min, DFW 17.6 min, CLT 17.2 min**.
* The 10 busiest origin airports have **33.4 % of flights and 34.9 % of delay minutes** - delay is roughly proportional to
  volume in aggregate, i.e. no single hub dominates the network problem.
* Cancellations: **Aspen 6.8 %** (mountain weather), Sarasota 3.6 %, Newark 2.5 %, LaGuardia 2.4 % (New York airspace).
* Worst routes (≥ 100 flights) are dominated by **San Juan (SJU)** connections (e.g. BDL→SJU 43.8 % delayed, BOS→SJU 38.1 %)
  and small-sample thin routes - treat route rankings as leads to investigate, not verdicts.

---

## 4. Recommendations (evidence → action)

| Evidence | Recommended action |
|---|---|
| Late-aircraft share rises from 14 % to 50 % during the day (F2) | Add turnaround buffer / spare aircraft to **afternoon-evening banks**; protect the last rotations of the day |
| 80 % of late departures arrive late; only 4.5 min recovered (F3) | Fix the problem **on the ground**: boarding, ground handling, gate readiness - the air leg cannot absorb it, especially on short hauls |
| Carrier cause = 34 % of delay minutes (F1) | Review crew scheduling, maintenance planning and ground-handling KPIs per airline/station |
| Extreme delays = 1.6 % of delayed flights but 14.8 % of minutes (F4) | Create an **irregular-operations (IROPS) recovery playbook**: faster re-accommodation, crew/aircraft re-positioning, proactive passenger comms |
| 10 days = 23 % of cancellations (F5) | Invest in **resilience for rare events** (IT failover, storm de-peaking, pre-emptive cancellations) rather than average-day tuning |
| Weather dominates cancellations but not delays (F6) | Weather-triggered **proactive cancellation / re-booking** policy; seasonal winter and summer-storm staffing |
| July/May/June and Fri/Sun peaks (F7) | Seasonal resourcing and schedule de-peaking; target extra buffers on peak days |
| Airline cause mixes differ (F8) | Tailor fixes: carrier-side (Hawaiian), NAS/airspace strategy (Spirit), rotation robustness (Frontier, Southwest) |

---

## 5. How the analysis was done

| Stage | What happens |
|---|---|
| Validate | Schema check of 33 required columns (fails fast with a clear message) |
| Clean | Typed columns, HHMM → minutes since midnight (`2400` → `0`), duplicate check (0 found), constant `year` dropped, cancellation code **kept** |
| Features | Route, airline names, hour/day-part, season, haul length, status labels, DOT delay flag, primary delay cause, minutes recovered, outlier flags, winsorized delays |
| Analyse | Reusable KPI functions: airline / airport / route / hour / month / day / cause / severity / event-day tables |
| Report | 28 interactive charts, 18 CSV tables, auto-generated `insights.md`, `data_quality_report.json` |

**Data-quality results on your file:** 0 duplicates · 0 missing times for completed flights · delay-cause minutes reconcile to arrival
delay for **100 %** of delayed flights · elapsed time = taxi-out + air + taxi-in for every completed flight.
Anomalies **flagged, not removed:** 4 impossible speeds (e.g. MIA→BOS 1,258 mi in 105 min), 162 extreme taxi times (e.g. a 444-min
taxi-in at DCA on the 15 Jan storm day), 23 schedule/actual time inconsistencies.

**A correction to the original notebooks:** they "imputed" 115 departure and 538 arrival times as missing values. Those are
exactly the counts of `2400` (midnight) in the raw file - parsing `2400` as a time failed, creating artificial nulls.
The new pipeline normalises `2400` → `0`, so no imputation is needed on this dataset (the imputation code remains as a safeguard).

---

## 6. What this project does NOT do (limitations)

**Scope of method**
1. **Descriptive/diagnostic only.** Findings are associations, not causal effects. There is **no predictive model**.
2. **Airline comparisons are not mix-adjusted.** Rankings do not control for each airline's airports, routes, hours or fleet,
   so some "worst airline" gaps may reflect network design (e.g. hub-heavy or Florida/Caribbean-heavy networks) rather than operational quality.
3. **No significance testing in the charts.** Confidence intervals were checked offline for airlines only; airport/route rankings
   (many with 100-1,000 sampled flights) are noisy and shown without error bars.
4. **Winsorization limits (0.5 / 99.5 percentile) and the 360-minute "extreme" threshold are judgement calls**, configurable but not validated against a cost model.

**Data gaps**
5. **Sample, not census:** 1M of ~7M flights - sampling error exists, and rare events (e.g. specific days or small airports) can be under- or over-represented.
6. **No tail number** → the knock-on (late-aircraft) effect is the carrier-reported bucket; real aircraft-rotation chains cannot be traced.
7. **No weather observations, airport capacity/ATC data, aircraft type, crew, passenger counts, fares or cost** → no dollar impact, no
   passenger-weighted metrics, no capacity-vs-demand diagnosis.
8. **Single year (2024):** seasonality and event effects cannot be separated from one-off 2024 events. Event explanations (IT outage, storms) are inferred from patterns, **not present in the data**.
9. **Cause codes are carrier-reported and only exist for delays ≥ 15 min;** shorter delays have no cause. The first-cause of a cascade is invisible.
10. **Diverted flights lack arrival data**, so they are excluded from delay statistics (reported separately, 0.24 %).
11. **Local times only:** no UTC conversion, so cross-time-zone hour comparisons use local clock time.

**Engineering**
12. Pandas in-memory design is right-sized for 1M rows (~25 s end to end) but **has not been tested on the full 7M rows**; that would need DuckDB/Polars or chunked processing.
13. Outputs are static HTML/CSV/markdown: **no dashboard, scheduler, data-versioning or monitoring**.

---

## 7. Future improvements (prioritised roadmap)

| Priority | Improvement | Value |
|---|---|---|
| **High** | Join **tail number** (full BTS file) to reconstruct aircraft rotations; quantify true propagation and size optimal turn buffers | Converts "late aircraft = 40 %" into an actionable scheduling rule |
| **High** | **Mix-adjusted airline benchmark** (regression / direct standardisation controlling for airport, route, hour, month) | Fair airline comparison |
| **High** | **Delay & cancellation risk model** (gradient boosting, time-based split, calibrated probabilities); strictly pre-departure features to avoid leakage (no dep delay, taxi, cause columns) | Predictive ops tool, passenger alerts |
| **High** | Add **confidence intervals / significance** to all rankings and use empirical-Bayes shrinkage for small airports/routes | Trustworthy leaderboards |
| Medium | Join **weather (METAR)** and **FAA ASPM airport capacity** | Separate weather vs congestion vs airline-controllable delay |
| Medium | **Cost model** (carrier's own cost per delay minute, compensation rules) | Dollar impact and ROI of recommendations |
| Medium | **Event/anomaly detection** on the daily series (change-point or robust z-score) with automated incident reports | Systematically find IROPS days |
| Medium | Run on the **full 7M rows** with DuckDB/Polars + Parquet partitioning; multi-year (2019-2024) trend and pre/post-event comparison | Scale and robustness |
| Medium | Geographic and network views (map of airport delay, hub-and-spoke flow graph); UTC-normalised time analysis | Insight on spatial propagation |
| Low | Streamlit/Dash dashboard; Prefect/Airflow scheduling; data validation with Great Expectations/Pandera; data versioning (DVC) | Production operations |
| Low | Passenger-weighted metrics (T-100 / DB1B) | Customer-centric KPIs |

---

## 8. Reproduce

```bash
pip install -e ".[dev]"
# place the CSV at data/raw/flight_random_1million.csv
python scripts/run_pipeline.py      # ~25 s on 1M rows
pytest                              # 26 tests
```
Outputs: `reports/insights.md` · `reports/tables/` · `reports/figures/` · `reports/data_quality_report.json`
