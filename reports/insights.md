# Airline Delay Intelligence - Auto-generated Insight Report

*Dataset: 1,000,000 scheduled flights. Delay = arrival >= 15 min late (DOT standard).*

## 1. Network health
- **On-time performance:** 79.15% of completed flights arrive within 15 min of schedule (20.85% are delayed).
- **Cancellations:** 1.36% | **Diversions:** 0.24%.
- **Average arrival delay:** 7.11 min (median -6.0); 90th percentile 43.0 min.
- When a flight *is* delayed it is late by **71.47 min** on average, accumulating **244,429 passenger-flight delay hours** in the sample.
- **Carry-over:** 80.5% of flights that depart >= 15 min late also arrive late, and they recover only 4.5 min on average in the air; 20.4% of late arrivals actually left on time.

## 2. What drives delays?
- **Late Aircraft** is the largest single cause, responsible for **40.16%** of delay minutes.

| Cause | Share of delay minutes (%) | Avg min / delayed flight |
|---|---|---|
| Late Aircraft | 40.16 | 28.7 |
| Carrier | 34.46 | 24.63 |
| NAS | 19.14 | 13.68 |
| Weather | 6.07 | 4.34 |
| Security | 0.17 | 0.12 |

## 3. Who performs worst? (airlines with enough volume)
| Airline | Flights | Delay rate % | Cancel rate % | Median arr delay (min) | Avg arr delay, winsorized (min) |
|---|---|---|---|---|---|
| Frontier Airlines | 29342 | 28.72 | 2.39 | -4.0 | 13.04 |
| American Airlines | 138835 | 26.16 | 1.56 | -4.0 | 12.0 |
| JetBlue Airways | 33913 | 25.62 | 1.56 | -6.0 | 9.46 |
| Spirit Airlines | 36964 | 23.66 | 1.92 | -6.0 | 7.36 |
| Alaska Airlines | 34705 | 21.98 | 1.91 | -4.0 | 4.18 |

Best performer on delay rate: **Republic Airways** (14.16%).

## 4. Airport and route bottlenecks
Origin airports with >= 500 flights, ranked by winsorized average departure delay:

| Airport | Flights | Avg dep delay, winsorized (min) | Delay rate % | Cancel rate % |
|---|---|---|---|---|
| ASE (Aspen) | 1099 | 24.3 | 30.88 | 6.82 |
| CRW (Charleston/Dunbar) | 500 | 20.34 | 25.25 | 1.6 |
| MIA (Miami) | 15579 | 17.96 | 28.1 | 1.88 |
| DFW (Dallas/Fort Worth) | 44306 | 17.59 | 27.06 | 1.91 |
| CLT (Charlotte) | 30411 | 17.18 | 27.41 | 1.37 |

Routes with >= 100 flights, ranked by winsorized average arrival delay:

| Route | Flights | Avg arr delay, winsorized (min) | Delay rate % |
|---|---|---|---|
| MFE → AUS | 102 | 32.9 | 28.71 |
| BDL → SJU | 145 | 29.35 | 43.75 |
| DFW → CAE | 115 | 28.46 | 38.6 |
| DFW → GRR | 165 | 27.58 | 35.58 |
| BOS → SJU | 302 | 26.38 | 38.05 |

## 5. When do disruptions happen?
- **Hour of day:** average departure delay is lowest at 06:00 (2.8 min) and highest at 20:00 (19.63 min) - delays snowball through the day as aircraft rotations run late.
- **Month:** delay rate peaks in month 7 (29.54%) and is lowest in month 10 (13.3%). Cancellations peak in month 1 (3.62%).
- **Weekday vs weekend:** delay rate 20.55% vs 21.63%.
- **Event-driven disruption:** the 10 worst days alone hold 23.3% of all cancellations (worst: 2024-07-19 with 17.32% cancelled).

| Date | Flights | Cancel rate % | Delay rate % |
|---|---|---|---|
| 2024-07-19 | 3084 | 17.32 | 57.64 |
| 2024-01-15 | 2592 | 15.55 | 49.75 |
| 2024-01-16 | 2274 | 13.1 | 52.79 |
| 2024-07-20 | 2763 | 11.29 | 38.88 |
| 2024-08-04 | 2987 | 10.98 | 35.9 |

- **Cascade evidence:** late-aircraft share of delay minutes rises from 13.72% for 06:00 departures to 49.67% for 20:00 departures.

## 6. Why are flights cancelled?
- Leading reason: **Weather** (55.59% of cancellations).

## 7. Outliers: small in number, large in impact
- 3,332 flights (0.339% of completed) were >= 360 min late, yet account for **13.84%** of all positive delay minutes.
- Mean arrival delay is 7.11 min raw vs 5.9 min winsorized (median -6.0); 74 flights were > 24 h late (max 3359 min).
- No rows were removed: extreme delays are real events; rankings use winsorized means.

| Severity | Flights | % of delayed flights | % of delay minutes |
|---|---|---|---|
| 15-59 min | 132813 | 64.72 | 28.0 |
| 60-179 min | 58118 | 28.32 | 39.47 |
| 180-359 min | 10933 | 5.33 | 17.77 |
| 360+ min (extreme) | 3332 | 1.62 | 14.76 |

## 8. Data quality
- Rows: 1,000,000 | cancelled: 13,608 | diverted: 2,359
- Delay-cause minutes that do not sum to arrival delay: 0.0%

> Interpretation note: results describe association, not causation. See docs/business_problem.md for scope and limitations.