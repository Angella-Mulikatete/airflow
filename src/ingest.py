from datetime import date, datetime, timezone
from pathlib import Path

from botocore.exceptions import ClientError

from src.config import RAW_BUCKET, SOURCE_DIR, s3_client


def raw_key_for(path: Path, run_date: date) -> str:
    return f"date={run_date.isoformat()}/{path.name}"


def already_ingested(client, key: str) -> bool:
    try:
        client.head_object(Bucket=RAW_BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def ingest_file(path: Path, run_date: date) -> str:
    client = s3_client()
    key = raw_key_for(path, run_date)

    if already_ingested(client, key):
        print(f"skip (already in raw zone): {key}")
        return key

    client.upload_file(
        str(path),
        RAW_BUCKET,
        key,
        ExtraArgs={
            "Metadata": {
                "source_file": path.name,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    print(f"ingested: {path.name} -> s3://{RAW_BUCKET}/{key}")
    return key


def run(run_date: date | None = None) -> list[str]:
    run_date = run_date or date.today()
    keys = [ingest_file(path, run_date) for path in sorted(Path(SOURCE_DIR).glob("*.csv"))]
    if not keys:
        print(f"no CSV files found in {SOURCE_DIR}")
    return keys


if __name__ == "__main__":
    run()
