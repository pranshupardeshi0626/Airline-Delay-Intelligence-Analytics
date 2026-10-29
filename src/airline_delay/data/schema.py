"""Expected raw schema of the BTS 2024 flight extract.

Keeping the schema in one place lets the loader fail fast if the input file is
not the dataset this pipeline was designed for.
"""
from __future__ import annotations

# Columns that MUST exist in the raw file for the pipeline to run.
REQUIRED_COLUMNS = [
    "month", "day_of_month", "day_of_week", "fl_date",
    "op_unique_carrier", "op_carrier_fl_num",
    "origin", "origin_city_name", "origin_state_nm",
    "dest", "dest_city_name", "dest_state_nm",
    "crs_dep_time", "dep_time", "dep_delay", "taxi_out", "wheels_off",
    "wheels_on", "taxi_in", "crs_arr_time", "arr_time", "arr_delay",
    "cancelled", "diverted",
    "crs_elapsed_time", "actual_elapsed_time", "air_time", "distance",
    "carrier_delay", "weather_delay", "nas_delay", "security_delay", "late_aircraft_delay",
]

# Optional columns (present in the Kaggle file, tolerated if missing).
OPTIONAL_COLUMNS = ["year", "cancellation_code"]

# Clock-time columns stored as HHMM (e.g. 1435 = 14:35).
HHMM_COLUMNS = ["crs_dep_time", "dep_time", "wheels_off", "wheels_on", "crs_arr_time", "arr_time"]

# Numeric columns measured in whole minutes.
MINUTE_COLUMNS = [
    "dep_delay", "arr_delay", "taxi_out", "taxi_in", "air_time",
    "crs_elapsed_time", "actual_elapsed_time",
    "carrier_delay", "weather_delay", "nas_delay", "security_delay", "late_aircraft_delay",
]

# The five BTS delay-cause columns (minutes attributed to each cause).
DELAY_CAUSE_COLUMNS = ["carrier_delay", "weather_delay", "nas_delay", "security_delay", "late_aircraft_delay"]
