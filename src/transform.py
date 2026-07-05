import io
import logging
from datetime import date
from pathlib import Path

import pandas as pd
from pandera.errors import SchemaErrors

from src.config import PROCESSED_BUCKET, QUARANTINE_DIR, RAW_BUCKET, s3_client
from src.schemas import KNOWN_PARAMETERS, processed_schema

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("transform")

SENSOR_ID = "IT-DEVICE-01"
MISSING_SENTINEL = -200


def _list_raw_keys(client, run_date: date) -> list[str]:
    prefix = f"date={run_date.isoformat()}/"
    resp = client.list_objects_v2(Bucket=RAW_BUCKET, Prefix=prefix)
    return [obj["Key"] for obj in resp.get("Contents", [])]


def _read_raw_csv(client, key: str) -> tuple[pd.DataFrame, dict]:
    obj = client.get_object(Bucket=RAW_BUCKET, Key=key)
    df = pd.read_csv(io.BytesIO(obj["Body"].read()), sep=";", decimal=",")
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    return df, obj.get("Metadata", {})


def _melt_to_long(df: pd.DataFrame, metadata: dict, key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    present = [c for c in KNOWN_PARAMETERS if c in df.columns]
    missing = [c for c in KNOWN_PARAMETERS if c not in df.columns]
    extra = [c for c in df.columns if c not in KNOWN_PARAMETERS and c not in ("Date", "Time")]
    if missing:
        log.warning(f"{key}: expected columns missing from source, skipping them: {missing}")
    if extra:
        log.warning(f"{key}: unrecognized columns in source, ignoring them: {extra}")

    timestamp = pd.to_datetime(
        df["Date"] + " " + df["Time"].str.replace(".", ":", regex=False),
        format="%d/%m/%Y %H:%M:%S",
        errors="coerce",
    )

    bad_rows = df.loc[timestamp.isna()].copy()
    bad_rows["quarantine_reason"] = "unparseable date/time"
    bad_rows["source_key"] = key

    good = df.loc[timestamp.notna()].copy()
    good["timestamp"] = timestamp.loc[timestamp.notna()]

    long_df = good.melt(id_vars=["timestamp"], value_vars=present, var_name="raw_column", value_name="value")
    long_df["parameter"] = long_df["raw_column"].map(lambda c: KNOWN_PARAMETERS[c][0])
    long_df["unit"] = long_df["raw_column"].map(lambda c: KNOWN_PARAMETERS[c][1])
    long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")
    long_df.loc[long_df["value"] == MISSING_SENTINEL, "value"] = pd.NA
    long_df = long_df.drop(columns=["raw_column"])

    long_df["sensor_id"] = SENSOR_ID
    long_df["source_file"] = metadata.get("source_file", key)
    long_df["ingested_at"] = metadata.get("ingested_at", "")

    return long_df, bad_rows


def _write_quarantine(frames: list[pd.DataFrame], run_date: date) -> None:
    frames = [f for f in frames if not f.empty]
    if not frames:
        return
    out = pd.concat(frames, ignore_index=True)
    path = Path(QUARANTINE_DIR) / f"{run_date.isoformat()}.csv"
    out.to_csv(path, index=False)
    log.warning(f"quarantined {len(out)} rows -> {path}")


def _write_processed(client, df: pd.DataFrame, run_date: date) -> None:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    key = f"date={run_date.isoformat()}/readings.parquet"
    client.put_object(Bucket=PROCESSED_BUCKET, Key=key, Body=buf.getvalue())
    log.info(f"wrote {len(df)} rows -> s3://{PROCESSED_BUCKET}/{key}")


def run(run_date: date | None = None) -> None:
    run_date = run_date or date.today()
    client = s3_client()
    keys = _list_raw_keys(client, run_date)
    if not keys:
        log.info(f"no raw files found for date={run_date.isoformat()}")
        return

    long_frames, quarantine_frames = [], []
    for key in keys:
        raw_df, metadata = _read_raw_csv(client, key)
        long_df, bad_rows = _melt_to_long(raw_df, metadata, key)
        long_frames.append(long_df)
        quarantine_frames.append(bad_rows)

    combined = pd.concat(long_frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["sensor_id", "timestamp", "parameter"], keep="last")

    try:
        validated = processed_schema.validate(combined, lazy=True)
    except SchemaErrors as e:
        failure_idx = e.failure_cases["index"].dropna().unique()
        failed_rows = combined.loc[failure_idx].copy()
        failed_rows["quarantine_reason"] = "schema validation failed"
        quarantine_frames.append(failed_rows)
        validated = combined.drop(index=failure_idx)
        log.warning(f"{len(failure_idx)} rows failed schema validation, quarantined")

    _write_quarantine(quarantine_frames, run_date)
    _write_processed(client, validated, run_date)


if __name__ == "__main__":
    run()
