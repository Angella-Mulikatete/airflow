import os
from functools import lru_cache

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_ENDPOINT_URL = os.environ.get(
    "R2_ENDPOINT_URL", f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
)
RAW_BUCKET = os.environ.get("R2_RAW_BUCKET", "airflow-ug-raw")
PROCESSED_BUCKET = os.environ.get("R2_PROCESSED_BUCKET", "airflow-ug-processed")

SOURCE_DIR = "data/incoming"
QUARANTINE_DIR = "data/quarantine"


@lru_cache
def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )
