from functools import lru_cache

import duckdb
import pandas as pd

from src.config import PROCESSED_BUCKET, R2_ACCESS_KEY_ID, R2_ACCOUNT_ID, R2_SECRET_ACCESS_KEY

PROCESSED_GLOB = f"s3://{PROCESSED_BUCKET}/*/*.parquet"


@lru_cache
def connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_endpoint='{R2_ACCOUNT_ID}.r2.cloudflarestorage.com';")
    con.execute(f"SET s3_access_key_id='{R2_ACCESS_KEY_ID}';")
    con.execute(f"SET s3_secret_access_key='{R2_SECRET_ACCESS_KEY}';")
    con.execute("SET s3_region='auto';")
    con.execute("SET s3_url_style='path';")
    return con


def query(sql: str, params: list | None = None) -> pd.DataFrame:
    return connection().execute(sql, params or []).df()
