import io
import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from src import transform
from src.config import PROCESSED_BUCKET, RAW_BUCKET, s3_client
from src.ingest import ingest_file

SCRATCH = Path("data/incoming/.chaos_scratch")
SOURCE = Path("data/incoming/AirQualityUCI.csv")
NEW_COLUMN_DATE = date(2099, 1, 1)
MISSING_COLUMN_DATE = date(2099, 1, 2)
REAL_DATE = date.today()


def _sample(n: int = 20) -> pd.DataFrame:
    df = pd.read_csv(SOURCE, sep=";", decimal=",")
    return df.dropna(axis=1, how="all").dropna(axis=0, how="all").head(n)


def _read_processed(client, run_date: date) -> pd.DataFrame:
    key = f"date={run_date.isoformat()}/readings.parquet"
    obj = client.get_object(Bucket=PROCESSED_BUCKET, Key=key)
    return pd.read_parquet(io.BytesIO(obj["Body"].read()))


def _cleanup(client, run_date: date) -> None:
    for bucket in (RAW_BUCKET, PROCESSED_BUCKET):
        prefix = f"date={run_date.isoformat()}/"
        resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        keys = [obj["Key"] for obj in resp.get("Contents", [])]
        if keys:
            client.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in keys]})


def test_new_column(client) -> None:
    print("=== Chaos test 1: source gains a new, unknown column ===")
    try:
        df = _sample()
        df["Battery_Voltage"] = 3.7
        path = SCRATCH / "chaos_new_column.csv"
        df.to_csv(path, sep=";", decimal=",", index=False)

        ingest_file(path, NEW_COLUMN_DATE)
        transform.run(NEW_COLUMN_DATE)
        result = _read_processed(client, NEW_COLUMN_DATE)

        expected_rows = len(df) * 13  # 13 known parameters; the new column is ignored, not crashed on
        assert len(result) == expected_rows, f"expected {expected_rows} rows, got {len(result)}"
        print(f"PASS: no crash, unknown column dropped, {len(result)} rows written (expected {expected_rows})\n")
    finally:
        _cleanup(client, NEW_COLUMN_DATE)


def test_missing_column(client) -> None:
    print("=== Chaos test 2: source loses an expected column ===")
    try:
        df = _sample().drop(columns=["NOx(GT)"])
        path = SCRATCH / "chaos_missing_column.csv"
        df.to_csv(path, sep=";", decimal=",", index=False)

        ingest_file(path, MISSING_COLUMN_DATE)
        transform.run(MISSING_COLUMN_DATE)
        result = _read_processed(client, MISSING_COLUMN_DATE)

        assert "nox" not in set(result["parameter"]), "dropped column should not appear as a parameter"
        expected_rows = len(df) * 12  # 12 remaining known parameters
        assert len(result) == expected_rows, f"expected {expected_rows} rows, got {len(result)}"
        print(f"PASS: no crash, missing column logged and skipped, {len(result)} rows written (expected {expected_rows})\n")
    finally:
        _cleanup(client, MISSING_COLUMN_DATE)


def test_double_run(client) -> None:
    print("=== Chaos test 3: rerun the same day's transform twice ===")
    transform.run(REAL_DATE)
    first = _read_processed(client, REAL_DATE)
    transform.run(REAL_DATE)
    second = _read_processed(client, REAL_DATE)

    assert len(first) == len(second), f"row count changed across reruns: {len(first)} -> {len(second)}"
    print(f"PASS: row count identical across reruns ({len(first)} rows both times)\n")


def run() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    client = s3_client()
    try:
        test_new_column(client)
        test_missing_column(client)
        test_double_run(client)
    finally:
        shutil.rmtree(SCRATCH, ignore_errors=True)
    print("All chaos tests passed.")


if __name__ == "__main__":
    run()
