# Learning Guide: Demystifying the AirFlow-UG Data Pipeline

This guide is designed to help you deconstruct the codebase and upskill in modern data engineering by understanding **what** was built, **why** it was built that way, and **how** you can reproduce it yourself step-by-step.

---

## 1. Glossary: Core Terms & Why They Matter

### Cloudflare R2 (Object Storage)
* **What is it?** A distributed, serverless object store (similar to AWS S3) that stores unstructured data (like files, images, or raw CSVs) rather than rows and columns.
* **Why it matters**: In modern data architectures, we split storage and compute. R2 serves as our "Data Lake." Storing data here is extremely cheap, has zero egress fees (unlike AWS), and allows us to scale storage infinitely without maintaining a database.

### Parquet (vs. CSV)
* **What is it?** CSV is a **row-oriented, text-based** format (easy for humans to read, but slow to process). Parquet is a **column-oriented, binary** format.
* **Why it matters**: 
  - If you only want to query a single column (e.g., `temperature`), a CSV reader must read the entire file line-by-line. A Parquet reader skips directly to that column's bytes.
  - Parquet is heavily compressed (often 10x smaller than CSV).
  - Parquet stores strict data types (it knows a column is a `Timestamp` or a `Float`), whereas CSV treats everything as text.

### Ingestion vs. Transformation (ELT/ETL)
* **What is it?** 
  - **Ingestion**: Moving raw, untouched files from a source (e.g., local folders, APIs) directly into the raw zone of the data lake (`airflow-ug-raw`).
  - **Transformation**: Cleaning, reshaping, validating, and rewriting the raw data into a structured output format (`airflow-ug-processed`).
* **Why it matters**: We keep raw data completely unmodified. If a bug is found in our cleaning code later, we can re-run the transformation against the raw files without needing to request the source system to resend the data.

### Idempotency
* **What is it?** A pipeline stage is **idempotent** if running it multiple times with the same input produces the exact same output without duplicating data or corrupting state.
* **Why it matters**: In production, pipelines fail due to network outages, API timeouts, or crashes. An idempotent pipeline can be safely retried. 
  - *Ingest idempotency*: Checks if `date=2026-07-05/AirQualityUCI.csv` already exists in R2; if yes, skip.
  - *Transform idempotency*: Overwrites the parquet file at the destination date rather than appending rows, so running it twice yields the same number of rows.

### Schema Drift & Resilience
* **What is it?** Schema drift happens when the upstream data source changes without warning (e.g., adding a new sensor column, dropping an old column, or altering a column name).
* **Why it matters**: Historically, a schema change would crash pipelines. By converting our table from a **wide** format (one column per sensor) to a **long** format (one row per reading), we make it resilient:
  - If a column is added, it is simply ignored because it isn't in our `KNOWN_PARAMETERS` map.
  - If a column goes missing, we log it and continue processing the rest, rather than throwing a fatal error.

### Pandera (Data Validation)
* **What is it?** A Python library that allows you to define schemas for pandas DataFrames and enforce checks (e.g., check that `value` is a float, `parameter` is one of our known names, and `(sensor_id, timestamp, parameter)` is a unique key).
* **Why it matters**: Without validation, silent corruptions leak to dashboards and APIs. Enforcing schema checks guarantees downstream applications never break.

### DuckDB & httpfs (Serverless Querying)
* **What is it?** DuckDB is an in-process SQL database engine optimized for analytical queries (OLAP). The `httpfs` extension allows DuckDB to read and run SQL directly on remote Parquet files over HTTP/S3 endpoints.
* **Why it matters**: There is no database server running 24/7 costing money. When FastAPI or Streamlit starts, they run an in-process DuckDB query that scans R2 Parquet files on demand. It is fast, cheap, and serverless.

---

## 2. Real-World Importance & Applications

### Why is this important in the industry?
1. **Massive Cost Reductions**: Standard cloud data architectures charge high fees for database compute (e.g., Snowflake, Redshift, AWS RDS) and data egress. Storing raw data in Cloudflare R2 (no egress fees) and querying it serverlessly via DuckDB bypasses costly database licensing and instances.
2. **Maintenance Simplicity**: Since there is no database server to maintain, upgrade, index, or back up, the architecture is virtually maintenance-free.
3. **Resilience Over Panic**: In a standard ETL pipeline, an upstream partner changing a column header wakes up engineers at 3:00 AM due to pipeline failure. In this design, the system logs the issue, quarantines only the corrupt records, and successfully writes the clean records.

### Real-World Scenarios & Applications
- **IoT Environmental and Industrial Telemetry**: Thousands of distributed sensors (temperature, pressure, quality) writing hourly CSV/JSON packets to object storage. The pipeline ingests, validates, cleans, and surfaces telemetry to factory monitoring dashboards.
- **FinTech / Bank Feed Integration**: Financial services ingesting raw transaction feeds from multiple banking partners. Different banks have different columns, and feeds often fail due to unexpected columns. This resilient schema-melting pipeline processes transactions reliably and flags anomalous structures for quarantine review.
- **AdTech Clickstream Tracking**: Tracking user clicks and impressions. If a new browser version sends an unexpected query parameter, the pipeline processes the clicks anyway without crashing.

---

## 3. Connecting the Blog "Practical Data Engineering" to AirFlow-UG

In Paweł Wiszniewski's blog post *Practical Data Engineering*, several industry standards are outlined. Here is how your AirFlow-UG project relates to and implements these concepts:

### A. The ETL Pattern Choice
* **Blog concept**: Paweł writes that for data under a few hundred thousand rows, Python-based **ETL (Extract-Transform-Load)** is highly effective, completing in under a minute.
* **AirFlow-UG application**: You chose the Python ETL model. `src/transform.py` performs in-memory data cleaning, unit conversions, and validation in seconds using Pandas and Pandera before saving to R2.

### B. Implementation of Technical Timestamps
* **Blog concept**: Paweł stresses that data systems *must* add technical timestamps (Extraction timestamp, Transformation timestamp, etc.) to trace records and identify which run processed the data.
* **AirFlow-UG application**: 
  - During **ingestion**, `src/ingest.py` tags the raw file with metadata: `"ingested_at": datetime.now(timezone.utc).isoformat()`.
  - During **transformation**, `src/transform.py` extracts that tag from R2 and appends it to every single row in the final Parquet file under the `ingested_at` column. This creates a perfect audit trail showing exactly when the data hit your data lake.

### C. Partitioning & Overwriting (Idempotency)
* **Blog concept**: The blog suggests that to avoid duplicates in daily/hourly runs, engineers must partition files and overwrite them on rerun.
* **AirFlow-UG application**: Your pipeline uses date-partitioned storage:
  - `date=<run_date>/<filename>` for raw CSVs.
  - `date=<run_date>/readings.parquet` for transformed data.
  - When you rerun the transform step, it does a full overwrite of that date's partition rather than an append, preventing data multiplication (ensuring **idempotency**).

### D. Full vs. Incremental Strategy
* **Blog concept**: Full downloads are simple, but incremental time-range downloads are used when data volumes are high. 
* **AirFlow-UG application**: Because air quality sensors dump complete daily files, your pipeline runs a daily batch ingestion (Full day snapshots). However, because of the partition setup, the architecture is already prepared to switch to an incremental time-range pull if you scale to hourly scheduling.

---

## 4. Major Key Takeaways
1. **Decouple Storage and Compute**: Store data in cheap, durable storage (like S3/R2 object storage) and bring compute engines (like DuckDB/Pandas) to the files when needed.
2. **Never Mutate the Raw Layer**: Raw data is your single source of truth. If your downstream transforms corrupt the data, you should always be able to blow away the processed zone and rebuild it from raw.
3. **Design for Failure (Idempotent & Resilient)**: Pipelines *will* fail. Code should assume that network requests will drop, runs will be executed twice, and source schemas will change. Write code that handles duplicates and anomalies gracefully.

---

## 5. Code Walkthrough of Major Files

### A. Ingestion (`src/ingest.py`)
This script acts as the entry point for raw files. It handles moving data from local storage/incoming folders to Cloudflare R2.
* **`already_ingested(client, key)`**: Runs a `head_object` check against R2. `head_object` retrieves only the HTTP headers of the file, avoiding downloading the entire body. If R2 returns a HTTP 200, the file is already there, and the script skips the upload (ensuring **idempotency**).
* **`ingest_file(path, run_date)`**: Uploads the file with `ExtraArgs={"Metadata": {...}}`. Stashing ingestion timestamps and original names in R2 object metadata allows us to trace back the origin of any parquet file without modifying the data itself.

### B. Transformation (`src/transform.py`)
This file is the core engine of the pipeline. It implements our cleanup, reshaping, validation, and quarantine logic.
* **`_melt_to_long(...)`**: 
  - Checks which columns from `KNOWN_PARAMETERS` exist in the raw DataFrame. 
  - Melts the wide format into a single column `parameter` and `value` (long format).
  - Handles the missing-value sentinel `-200` by converting it to `NaN`/`None`.
  - Isolates rows with unparseable timestamps into `bad_rows` DataFrame.
* **`run(...)`**:
  - Concatenates processed dataframes from all files.
  - Drops duplicate combinations of `[sensor_id, timestamp, parameter]` to maintain data uniqueness.
  - Wraps schema validation in a `try-except SchemaErrors` block. Valid rows are written as a Parquet file, and failing indices are dropped and saved separately to the local quarantine directory.

### C. Querying (`src/query.py`)
This file initializes our query capability.
* **`connection()`**: Connects to an in-process, transient DuckDB database, installs and loads the `httpfs` extension, and configures the credentials to read S3/R2 directly. It uses Python's `@lru_cache` to ensure that only a single, persistent connection is opened, reusing it across different API queries to save socket connection overhead.
* **`query(sql, params)`**: Takes parameterized SQL (using `?` placeholders to prevent SQL injection vulnerabilities) and executes it, converting results directly back to a Pandas DataFrame.

### D. API (`api/main.py`)
Exposes our data lake over HTTP endpoints using FastAPI.
* **`/readings`**: Employs DuckDB SQL functions like `read_parquet('s3://...')` to scan processed parquet files directly on the fly. It constructs a dynamic `WHERE` clause depending on the filters provided (`sensor_id`, `parameter`, `date`) and limits the row count to prevent memory overflow.

### E. Dashboard (`dashboard/app.py`)
Streamlit frontend for visual analytics.
* **`@st.cache_data(ttl=60)`**: Caches raw data queries inside the web server's memory for 60 seconds. This is critical—without caching, every mouse click or select-box change by a user triggers a fresh, expensive network scan to Cloudflare R2. Caching makes the user experience lightning-fast.

---

## 6. Step-by-Step Roadmap to Rebuild This Yourself

If you want to master this, **delete your local code (keep it pushed on GitHub)** and build it again piece by piece:

### Step 1: Environment & Config
1. Create a virtual environment (`python -m venv .venv`).
2. Set up `.env` with R2 credentials.
3. Write `src/config.py`. Learn how `boto3` initializes an S3 client using custom `endpoint_url` values.

### Step 2: The Ingestion Script (`src/ingest.py`)
1. Write a function to check if an object exists in R2 (`client.head_object`).
2. Write an upload function (`client.upload_file`) that includes custom metadata (like the upload time).
3. Test uploading `data/incoming/AirQualityUCI.csv` to R2.

### Step 3: Reshaping the Data (`src/transform.py`)
1. Read the raw CSV from R2 using `pd.read_csv`.
2. Convert Date/Time columns into a single `datetime64[ns]` object. Try parsing bad formats.
3. Learn how `pd.melt` works. This is the magic that converts:
   - **Wide**: `[Date, Time, CO, NO2]` 
   - **Long**: `[Timestamp, Parameter, Value]`
4. Map the raw column names to clean parameters and units.

### Step 4: Validation & Quarantining (`src/schemas.py`)
1. Create a Pandera `DataFrameSchema`. Add validations like checking if fields are non-null and validating unique keys.
2. In your transform script, catch `SchemaErrors`.
3. Separate rows that failed validation. Save them locally in a `quarantine/` CSV file, and write the valid rows to a Parquet buffer (`df.to_parquet`).
4. Upload the Parquet file to the processed R2 bucket.

### Step 5: Querying R2 via DuckDB (`src/query.py`)
1. Initialize a DuckDB connection.
2. Run `INSTALL httpfs; LOAD httpfs;` and set the S3 endpoint configuration keys.
3. Write a helper function that executes SQL queries against `s3://YOUR_BUCKET/*/*.parquet` and returns a pandas DataFrame.

### Step 6: Presentation (FastAPI & Streamlit)
1. Write `api/main.py` using FastAPI. Create endpoints that run parameterized SQL queries using your DuckDB helper.
2. Write `dashboard/app.py` using Streamlit. Use `st.line_chart` and `st.metric` to display data. Use `@st.cache_data` to ensure you aren't hitting R2 on every page refresh.

### Step 7: Automation & Testing
1. Write a `Makefile` to simplify running commands (`make run`, `make serve`).
2. Write a chaos test (`scripts/chaos_test.py`) that intentionally adds bad data to check if your pipeline handles it.

---

## 7. High-Value Tasks for Upskilling

Try editing the project on your own branch to practice:
* **Task 1**: Add a new validation rule to the Pandera schema (e.g. temperature must be between -50°C and 60°C). Run `make chaos` to verify that invalid temperatures are quarantined.
* **Task 2**: Add a new API endpoint in `api/main.py` that returns the daily maximum values for a parameter.
* **Task 3**: Create a new chart in the Streamlit dashboard that shows a comparison between two parameters (like `co` vs `nox_sensor_response`).
