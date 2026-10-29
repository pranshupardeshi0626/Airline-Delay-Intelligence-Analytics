# Business Problem Framing

## 1. Context

The dataset is a **1-million-flight random sample of 2024 US domestic scheduled flights**
(U.S. Bureau of Transportation Statistics on-time data, via Kaggle `hrishitpatil/flight-data-2024`), randomly drawn from ~7 million flights.
It covers **15 operating carriers, 348 airports and 6,588 directional routes** across all 12 months,
with departure/arrival delays, taxi times, the five official BTS **delay-cause buckets**
(carrier, weather, NAS, security, late aircraft), and **cancellation / diversion** flags with reason codes.

A late or cancelled flight is expensive for everyone involved: it burns aircraft and crew time, triggers
passenger compensation and re-booking, breaks the next flight in the aircraft's rotation, and erodes loyalty.
The cause columns in this dataset let us separate **what the airline controls** (carrier delay, much of
late-aircraft knock-on) from **what it only partly controls** (NAS/airspace, weather).

## 2. Stakeholders and decisions

| Stakeholder | Decision they need to make | What this project gives them |
|---|---|---|
| **VP Network Operations / Operations Control Center** | Where and when to add schedule buffer, spare aircraft and crew | High-risk hours, months and airports; cascade (late-aircraft) share |
| **Schedule Planning** | Which rotations/banks to re-time or de-peak | Hour x month and weekday x hour risk heatmaps; route-level reliability |
| **Airport / Station Managers** | Where ground handling and turn performance need investment | Airport ranking by departure delay and cancellation rate, with minimum-volume filter |
| **Customer Experience / Revenue** | Which flights to proactively re-accommodate or compensate | Cancellation reasons and the delay-tail (P90) per airline and route |
| **Industry / Benchmark analyst** | How carriers compare on a like-for-like basis | Airline scorecard: delay rate vs cancellation rate vs volume |

## 3. Core problem statement

> **How can an airline operations team reduce arrival delays and cancellations by identifying *which causes, carriers,
> airports, routes and time windows* generate the most disruption - and which of those levers are controllable?**

## 4. Business questions -> analysis -> KPI

| # | Business question | Analysis in this repo | KPI |
|---|---|---|---|
| Q1 | How reliable is the network overall? | `network_kpis` | On-time % (arrival < 15 min), cancel %, divert %, P90 delay |
| Q2 | What drives delay minutes? | `delay_cause_summary` (network, by airline, by month) | Share of delay minutes by cause |
| Q3 | How much of the problem is knock-on (late aircraft) vs. self-inflicted (carrier)? | cause mix + hourly delay build-up | Late-aircraft share, delay by hour |
| Q4 | Which airlines are least reliable *at comparable volume*? | `airline_kpis`, scorecard chart | Delay rate, cancel rate, avg arr delay |
| Q5 | Which airports and routes are bottlenecks? | `airport_kpis`, `route_kpis` (min-volume filtered) | Avg dep delay, delay rate, cancel rate |
| Q6 | When are disruptions concentrated? | hour, month, weekday x hour, month x hour heatmaps | Delay rate / avg delay by window |
| Q7 | Why do flights get cancelled? | `cancellation_reasons`, airline x month cancel heatmap | Cancellations by reason code |
| Q8 | Do pilots recover time en route? | `delay_recovered` by haul length | Minutes recovered after a late departure |

## 5. Success metrics (what "better" means)

* On-time arrival rate up, *and* P90 arrival delay down (customers feel the tail, not the average).
* Share of delay minutes attributable to **carrier** + **late aircraft** down (the controllable portion).
* Cancellation rate down in the high-risk months identified by the analysis.

## 6. Scope, assumptions and limitations

* **Descriptive / diagnostic analytics (EDA).** Findings show association, not causation.
* **Sample, not census:** 1M rows is a random subset (~1 in 7) of the full-year US flight population; rankings for small
  airports/routes are noisy, so leaderboards enforce minimum flight counts (configurable in `config/config.yaml`).
* **"Delayed" follows the DOT convention:** arrival >= 15 minutes after schedule. Cancelled and diverted flights are
  excluded from on-time % (reported separately) rather than silently counted as on time.
* **Cause columns are only populated for flights >= 15 min late** and are carrier-reported; the late-aircraft bucket
  records *that* an earlier delay propagated, not *who* caused the first delay.
* **No tail number, weather observations, passenger counts or cost data** in the file, so aircraft-level
  propagation chains, weather modelling and dollar impact cannot be derived here.

## 7. Recommended follow-ups

1. Join **tail number** to measure the real rotation-level cascade and size optimal turnaround buffers.
2. Join **METAR weather** and **FAA ASPM** airport capacity to separate demand-capacity imbalance from weather.
3. Add a **cost model** (carrier's own cost per delay minute, compensation rules) to convert minutes to dollars.
4. Build a **delay / cancellation risk model** (gradient boosting with time-based train/test split, calibrated
   probabilities) using the features engineered in `src/airline_delay/features`.
   Departure delay, taxi and cause columns must be excluded to avoid target leakage for pre-departure prediction.
