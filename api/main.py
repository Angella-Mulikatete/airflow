from datetime import date

import pandas as pd
from fastapi import FastAPI, Query

from src.query import PROCESSED_GLOB, query

app = FastAPI(title="AirFlow-UG")


def _records(df: pd.DataFrame) -> list[dict]:
    return df.astype(object).where(df.notnull(), None).to_dict(orient="records")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/readings")
def readings(
    sensor_id: str | None = None,
    parameter: str | None = None,
    on_date: date | None = Query(None, alias="date"),
    limit: int = Query(500, le=5000),
):
    clauses, params = [], []
    if sensor_id:
        clauses.append("sensor_id = ?")
        params.append(sensor_id)
    if parameter:
        clauses.append("parameter = ?")
        params.append(parameter)
    if on_date:
        clauses.append("CAST(timestamp AS DATE) = ?")
        params.append(on_date)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT sensor_id, timestamp, parameter, value, unit
        FROM read_parquet('{PROCESSED_GLOB}')
        {where}
        ORDER BY timestamp
        LIMIT {limit}
    """
    df = query(sql, params)
    df["timestamp"] = df["timestamp"].astype(str)
    return _records(df)


@app.get("/summary/daily")
def summary_daily(parameter: str | None = None):
    clauses, params = [], []
    if parameter:
        clauses.append("parameter = ?")
        params.append(parameter)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    sql = f"""
        SELECT
            CAST(timestamp AS DATE) AS reading_date,
            parameter,
            ROUND(AVG(value), 3) AS avg_value,
            MIN(value) AS min_value,
            MAX(value) AS max_value,
            COUNT(*) AS n_readings
        FROM read_parquet('{PROCESSED_GLOB}')
        {where}
        GROUP BY reading_date, parameter
        ORDER BY reading_date, parameter
    """
    df = query(sql, params)
    df["reading_date"] = df["reading_date"].astype(str)
    return _records(df)
