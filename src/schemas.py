from pandera.pandas import Check, Column, DataFrameSchema

# raw column name -> (clean parameter name, unit)
KNOWN_PARAMETERS = {
    "CO(GT)": ("co", "mg_m3"),
    "PT08.S1(CO)": ("co_sensor_response", "unitless"),
    "NMHC(GT)": ("nmhc", "ug_m3"),
    "C6H6(GT)": ("benzene", "ug_m3"),
    "PT08.S2(NMHC)": ("nmhc_sensor_response", "unitless"),
    "NOx(GT)": ("nox", "ppb"),
    "PT08.S3(NOx)": ("nox_sensor_response", "unitless"),
    "NO2(GT)": ("no2", "ug_m3"),
    "PT08.S4(NO2)": ("no2_sensor_response", "unitless"),
    "PT08.S5(O3)": ("o3_sensor_response", "unitless"),
    "T": ("temperature", "celsius"),
    "RH": ("relative_humidity", "percent"),
    "AH": ("absolute_humidity", "g_m3"),
}

PARAMETER_NAMES = sorted({parameter for parameter, _ in KNOWN_PARAMETERS.values()})

processed_schema = DataFrameSchema(
    {
        "sensor_id": Column(str, nullable=False),
        "timestamp": Column("datetime64[ns]", nullable=False),
        "parameter": Column(str, Check.isin(PARAMETER_NAMES), nullable=False),
        "value": Column(float, nullable=True),
        "unit": Column(str, nullable=False),
        "source_file": Column(str, nullable=False),
        "ingested_at": Column(str, nullable=False),
    },
    unique=["sensor_id", "timestamp", "parameter"],
    coerce=True,
)
