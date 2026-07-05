# AirFlow-UG (Air Quality Pipeline)

Cloud data pipeline: raw air-quality sensor CSV → validated Parquet in Cloudflare R2 → queryable via DuckDB → served through an API/dashboard.

## Overview
AirFlow-UG is a production-grade, end-to-end cloud data ingestion and transformation pipeline designed to handle raw environmental sensor telemetry. The pipeline processes raw air quality data from roadside devices (UCI Air Quality Dataset), transforms the wide sensor-specific table into a clean, long-format schema, and hosts the results in a cost-effective cloud data lake. Downstream clients can immediately explore the data via a FastAPI web service or an interactive Streamlit dashboard.

## Key Technical Highlights
- **Idempotent Ingestion & Storage**: Checks file existence via AWS S3-compatible metadata headers before uploading to Cloudflare R2 (`raw` bucket) to avoid duplicate writes.
- **Schema Resilience (Survival of Schema Drift)**: Designed to withstand real-world source changes. It gracefully skips and logs missing expected columns and ignores new, unrecognized columns without crashing the execution.
- **Strict Pandera Validation & Quarantine**: Validates data types, ranges, and primary key uniqueness. Rows containing corrupt timestamps or failing validation are automatically isolated into a quarantine directory for auditing, preventing contaminated data from entering the production zone.
- **Zero-Server Querying (DuckDB & R2)**: Instead of provisioning and maintaining a heavy database server, the project uses DuckDB's `httpfs` extension to run SQL queries directly over date-partitioned Parquet files stored in the R2 `processed` bucket, yielding sub-second query times.
- **Interactive Frontend & API**: A FastAPI serving layer and a real-time Streamlit dashboard let users filter and plot hourly parameters, track daily summaries, and inspect data completeness.
- **Automated Chaos Testing**: Includes a custom chaos harness (`scripts/chaos_test.py`) that simulates malformed datasets to verify error-handling logic and ensure 100% pipeline reliability.

---

## Status

Pipeline is fully functional and verified.

- [x] Repo skeleton
- [x] Source data: [UCI Air Quality Dataset](https://archive.ics.uci.edu/dataset/360/air+quality) in `data/incoming/`
- [x] Cloudflare R2 Storage configuration
- [x] `src/ingest.py` — source → raw zone
- [x] `src/transform.py` — raw → processed zone
- [x] Queryable store (DuckDB over R2)
- [x] `api/main.py` — serving layer (FastAPI)
- [x] `dashboard/app.py` — visualization layer (Streamlit)
- [x] Chaos testing (`scripts/chaos_test.py`)
- [x] `docs/architecture.md`, `docs/schema.md`

## Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env   # fill in R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
```

## Source data

`data/incoming/AirQualityUCI.csv` — hourly gas-sensor readings from a roadside device in an Italian city, March 2004–February 2005. Known quirks handled by the pipeline: `;`-delimited, comma decimals, `-200` missing-value sentinel, trailing empty columns/rows from the original Excel export.
