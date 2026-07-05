# AirFlow-UG

Cloud data pipeline: raw air-quality sensor CSV → validated Parquet in Azure Data Lake → queryable via DuckDB → served through an API/dashboard.

## Status

Scaffolding stage. Build order (see `docs/` as each piece lands):

- [x] Repo skeleton
- [x] Source data: [UCI Air Quality Dataset](https://archive.ics.uci.edu/dataset/360/air+quality) in `data/incoming/`
- [ ] Azure Storage account (containers: `raw`, `processed`)
- [ ] `src/ingest.py` — source → raw zone
- [ ] `src/transform.py` — raw → processed zone
- [ ] Queryable store (DuckDB over ADLS)
- [ ] `api/main.py` — serving layer
- [ ] Orchestration (Makefile + GitHub Actions cron)
- [ ] Chaos tests
- [ ] `docs/architecture.md`, `docs/schema.md`

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in AZURE_STORAGE_CONNECTION_STRING
```

## Source data

`data/incoming/AirQualityUCI.csv` — hourly gas-sensor readings from a roadside device in an Italian city, March 2004–February 2005. Known quirks handled by the pipeline: `;`-delimited, comma decimals, `-200` missing-value sentinel, trailing empty columns/rows from the original Excel export.
