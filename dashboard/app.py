import streamlit as st

from src.query import PROCESSED_GLOB, query
from src.schemas import PARAMETER_NAMES

st.set_page_config(page_title="AirFlow-UG", layout="wide")
st.title("AirFlow-UG — Air Quality Pipeline")
st.caption("Raw sensor CSV -> validated Parquet on Cloudflare R2 -> queried live via DuckDB")


@st.cache_data(ttl=60)
def load_readings(parameter: str):
    sql = f"""
        SELECT timestamp, value, unit
        FROM read_parquet('{PROCESSED_GLOB}')
        WHERE parameter = ?
        ORDER BY timestamp
    """
    return query(sql, [parameter])


@st.cache_data(ttl=60)
def load_daily_summary(parameter: str):
    sql = f"""
        SELECT
            CAST(timestamp AS DATE) AS reading_date,
            ROUND(AVG(value), 3) AS avg_value,
            MIN(value) AS min_value,
            MAX(value) AS max_value,
            COUNT(*) AS n_readings,
            SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) AS n_missing
        FROM read_parquet('{PROCESSED_GLOB}')
        WHERE parameter = ?
        GROUP BY reading_date
        ORDER BY reading_date
    """
    return query(sql, [parameter])


parameter = st.selectbox("Parameter", PARAMETER_NAMES, index=PARAMETER_NAMES.index("co"))

readings = load_readings(parameter)
daily = load_daily_summary(parameter)
unit = readings["unit"].dropna().iloc[0] if not readings["unit"].dropna().empty else "unitless"

total = len(readings)
missing = readings["value"].isna().sum()
col1, col2, col3 = st.columns(3)
col1.metric("Total readings", f"{total:,}")
col2.metric("Missing readings", f"{missing:,}", f"{missing / total:.1%}" if total else "0%")
col3.metric("Unit", unit)

st.subheader(f"Hourly {parameter} over time")
st.line_chart(readings.set_index("timestamp")["value"])

st.subheader(f"Daily average {parameter}")
st.line_chart(daily.set_index("reading_date")["avg_value"])

st.subheader("Daily summary table")
st.dataframe(daily, width="stretch")
