# Data Dictionary

## Raw columns (BTS on-time performance, 2024)

| Column | Type | Description |
|---|---|---|
| `year`, `month`, `day_of_month`, `day_of_week` | int | Calendar fields; `day_of_week` 1 = Monday ... 7 = Sunday. `year` is constant (2024) and dropped. |
| `fl_date` | date | Flight date |
| `op_unique_carrier` | str | Two-character airline code (e.g. `DL`) |
| `op_carrier_fl_num` | float->str | Flight number |
| `origin`, `dest` | str | IATA airport codes |
| `origin_city_name`, `dest_city_name`, `origin_state_nm`, `dest_state_nm` | str | Airport city and state |
| `crs_dep_time`, `crs_arr_time` | HHMM | *Scheduled* departure / arrival local time |
| `dep_time`, `wheels_off`, `wheels_on`, `arr_time` | HHMM | *Actual* clock events (blank for cancelled flights) |
| `dep_delay`, `arr_delay` | min | Actual minus scheduled; negative = early |
| `taxi_out`, `taxi_in`, `air_time` | min | Ground and airborne durations |
| `crs_elapsed_time`, `actual_elapsed_time` | min | Scheduled / actual gate-to-gate time |
| `distance` | miles | Great-circle distance |
| `cancelled`, `diverted` | 0/1 | Disruption flags |
| `cancellation_code` | A-D | A Carrier, B Weather, C National Air System, D Security. Blank when not cancelled (**by design**) |
| `carrier_delay`, `weather_delay`, `nas_delay`, `security_delay`, `late_aircraft_delay` | min | Delay minutes attributed to each cause. Only meaningful for flights arriving >= 15 min late; sums to `arr_delay` |

## Engineered features (`src/airline_delay/features/engineering.py`)

| Feature | Definition | Business use |
|---|---|---|
| `arrival_status`, `departure_status` | Cancelled / Diverted / Early / On Time / Late | Status mix |
| `is_arr_delayed`, `is_dep_delayed` | 1 if delay >= 15 min; `<NA>` for cancelled/diverted | On-time KPI without bias |
| `delay_recovered` | `dep_delay - arr_delay` | Time made up en route |
| `primary_delay_cause` | Largest cause bucket for delayed flights | Root-cause segmentation |
| `route` | `ORIGIN -> DEST` | Route reliability |
| `airline_name`, `origin_label`, `dest_label` | Readable names | Reporting |
| `scheduled_dep_hour`, `actual_dep_hour` | 0-23 | Peak-hour analysis |
| `dep_daypart` | Red-eye / Morning / Afternoon / Evening / Night | Time-of-day segments |
| `is_weekend`, `day_type`, `day_name`, `month_name`, `season` | Calendar flags | Seasonality |
| `haul` | Short / Medium / Long by distance | Haul-length comparison |
| `cancellation_reason` | Readable cancellation code (A/B/C present in this sample; no D) | Cancellation root cause |
| `is_extreme_delay` | 1 if arrival delay ≥ 360 min (completed flights) | Outlier tracking |
| `arr_delay_w`, `dep_delay_w` | Delay clipped to the 0.5-99.5 percentile (data-driven caps) | Robust averages and rankings |
| `is_speed_anomaly` | Implied speed (distance ÷ air time) outside 50-700 mph | Data-quality review |
| `is_taxi_anomaly` | Taxi-out > 180 min or taxi-in > 120 min | Data-quality review |
| `is_time_inconsistent` | Actual clock time ≠ scheduled time + reported delay (mod 24 h) | Data-quality review |

Clock columns are stored as **minutes since midnight** after cleaning (e.g. 14:35 -> 875).
