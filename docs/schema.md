# Schema

## Raw schema (as delivered by the source)

`data/incoming/AirQualityUCI.csv` — `;`-delimited, comma decimals, one row per hour.

| Column | Type (as parsed) | Nullable | Description | Example |
|---|---|---|---|---|
| `Date` | string, `DD/MM/YYYY` | no | Reading date | `10/03/2004` |
| `Time` | string, `HH.MM.SS` | no | Reading time (dots, not colons) | `18.00.00` |
| `CO(GT)` | float, comma decimal | sentinel `-200` | Reference CO concentration | `2,6` |
| `PT08.S1(CO)` | int | sentinel `-200` | Tin-oxide sensor response (CO-targeted) | `1360` |
| `NMHC(GT)` | float | sentinel `-200` | Reference non-methane hydrocarbons | `150` |
| `C6H6(GT)` | float, comma decimal | sentinel `-200` | Reference benzene concentration | `11,9` |
| `PT08.S2(NMHC)` | int | sentinel `-200` | Sensor response (NMHC-targeted) | `1046` |
| `NOx(GT)` | float | sentinel `-200` | Reference NOx concentration | `166` |
| `PT08.S3(NOx)` | int | sentinel `-200` | Sensor response (NOx-targeted) | `1056` |
| `NO2(GT)` | float | sentinel `-200` | Reference NO2 concentration | `113` |
| `PT08.S4(NO2)` | int | sentinel `-200` | Sensor response (NO2-targeted) | `1692` |
| `PT08.S5(O3)` | int | sentinel `-200` | Sensor response (O3-targeted) | `1268` |
| `T` | float, comma decimal | sentinel `-200` | Temperature (°C) | `13,6` |
| `RH` | float, comma decimal | sentinel `-200` | Relative humidity (%) | `48,9` |
| `AH` | float, comma decimal | sentinel `-200` | Absolute humidity | `0,7578` |
| *(2 trailing columns)* | empty | always | Artifact of the original Excel export | dropped in transform |

`-200` is the source's own missing-value sentinel (not a real reading) — see `src/schemas.py::MISSING_SENTINEL`.

## Processed schema (enforced by `src/schemas.py::processed_schema`)

Long format: one row per `(sensor_id, timestamp, parameter)` reading. Written as Parquet to `s3://airflow-ug-processed/date=<run_date>/readings.parquet`.

| Column | Type | Nullable | Description | Example |
|---|---|---|---|---|
| `sensor_id` | string | no | Device identifier (constant `IT-DEVICE-01` for this source; the schema supports adding more sensors without changes) | `IT-DEVICE-01` |
| `timestamp` | datetime64 | no | Combined `Date` + `Time`, parsed | `2004-03-10 18:00:00` |
| `parameter` | string, one of 13 known values (`Check.isin`) | no | Clean parameter name — see mapping below | `co` |
| `value` | float | yes — `-200` sentinel becomes null | The reading itself | `2.6` |
| `unit` | string | no | Unit of the reading, or `unitless` for raw sensor-response columns | `mg_m3` |
| `source_file` | string | no | Which raw file produced this row | `AirQualityUCI.csv` |
| `ingested_at` | string (ISO 8601 UTC) | no | When `ingest.py` wrote the source file to the raw zone | `2026-07-05T16:22:03+00:00` |

Enforced constraint: `(sensor_id, timestamp, parameter)` is unique — pandera's `unique=` check fails the row (routed to quarantine) rather than silently allowing duplicates through.

## Raw column → parameter/unit mapping

| Raw column | `parameter` | `unit` |
|---|---|---|
| `CO(GT)` | `co` | `mg_m3` |
| `PT08.S1(CO)` | `co_sensor_response` | `unitless` |
| `NMHC(GT)` | `nmhc` | `ug_m3` |
| `C6H6(GT)` | `benzene` | `ug_m3` |
| `PT08.S2(NMHC)` | `nmhc_sensor_response` | `unitless` |
| `NOx(GT)` | `nox` | `ppb` |
| `PT08.S3(NOx)` | `nox_sensor_response` | `unitless` |
| `NO2(GT)` | `no2` | `ug_m3` |
| `PT08.S4(NO2)` | `no2_sensor_response` | `unitless` |
| `PT08.S5(O3)` | `o3_sensor_response` | `unitless` |
| `T` | `temperature` | `celsius` |
| `RH` | `relative_humidity` | `percent` |
| `AH` | `absolute_humidity` | `g_m3` |

This mapping (`src/schemas.py::KNOWN_PARAMETERS`) is the single source of truth for schema evolution: a raw column not in this table is ignored (new-column drift), and a table entry missing from the raw file simply produces no rows for that parameter (dropped-column drift). See `docs/architecture.md` for the full behavior table.
