# AirFlow-UG

Cloud data pipeline: raw air-quality sensor CSV → validated Parquet on Cloudflare R2 → queryable via DuckDB → served through a FastAPI and a Streamlit dashboard.

See [`docs/architecture.md`](docs/architecture.md) for the data flow diagram and design rationale, and [`docs/schema.md`](docs/schema.md) for column definitions.

## Setup (clean machine, ~2 minutes measured — `git clone` to `make run`)

```
git clone <this-repo>
cd airflow-ug
make setup
cp .env.example .env   # fill in R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
```

`R2_ACCOUNT_ID`/`R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY` come from a Cloudflare R2 API token (dashboard → R2 Object Storage → Manage R2 API Tokens). Two buckets must exist: `airflow-ug-raw` and `airflow-ug-processed` (create via the dashboard, or `aws s3 mb` pointed at the R2 S3-compatible endpoint).

## Run

```
make run        # ingest -> transform, single command, idempotent
make serve      # FastAPI on :8000 (GET /health, /readings, /summary/daily)
make dashboard  # Streamlit dashboard on :8501
make chaos      # schema-drift + idempotency tests against live storage
```

A GitHub Actions workflow (`.github/workflows/pipeline.yml`) runs `make setup && make run` hourly via cron and on manual dispatch — the scheduled trigger requires the three `R2_*` values as repository secrets.

## Source data

`data/incoming/AirQualityUCI.csv` — hourly gas-sensor readings from a roadside device in an Italian city, March 2004–February 2005 ([UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/360/air+quality)). Known quirks handled by the pipeline: `;`-delimited, comma decimals, `-200` missing-value sentinel, trailing empty columns/rows from the original Excel export.
