from __future__ import annotations

from typing import Dict

import pandas as pd
from src import config
from src.utils import (
    find_parameter_columns,
    get_parameter_info,
    parse_concentration,
    split_parameter_column,
)


class ValidationError(Exception):
    pass


def validate_chem_sheet(
    chem_df: pd.DataFrame,
) -> list[str]:

    missing = set(config.CHEM_REQUIRED_COLUMNS) - set(chem_df.columns)

    if missing:

        raise ValidationError(
            "Missing required chemistry columns: " f"{sorted(missing)}"
        )

    parameter_columns = find_parameter_columns(chem_df)

    if len(parameter_columns) == 0:

        raise ValidationError("No parameter columns found.")

    for col in parameter_columns:

        try:

            split_parameter_column(col)

        except Exception:

            raise ValidationError(f"Invalid parameter column: " f"{col}")

    return parameter_columns


def validate_flow_sheet(
    flow_df: pd.DataFrame,
):

    missing = set(config.FLOW_REQUIRED_COLUMNS) - set(flow_df.columns)

    if missing:

        raise ValidationError("Missing required flow columns: " f"{sorted(missing)}")

    flow = pd.to_numeric(
        flow_df["flow_m3/s"],
        errors="coerce",
    )

    if flow.isna().any():

        raise ValidationError("Flow data contains non-numeric values.")

    if (flow < 0).any():

        raise ValidationError("Flow data contains negative values.")


def validate_dates(
    chem_df: pd.DataFrame,
    flow_df: pd.DataFrame,
):

    try:

        chem_df["date"] = pd.to_datetime(chem_df["date"])

    except Exception:

        raise ValidationError("Invalid dates found in chem sheet.")

    try:

        flow_df["date"] = pd.to_datetime(flow_df["date"])

    except Exception:

        raise ValidationError("Invalid dates found in flow sheet.")

    return chem_df, flow_df


def validate_concentrations(
    chem_df: pd.DataFrame,
    parameter_columns: list[str],
):

    for col in parameter_columns:

        values = chem_df[col].dropna().tolist()

        for value in values:

            try:

                parse_concentration(value)

            except Exception:

                raise ValidationError(
                    f"Invalid concentration value '{value}' in column '{col}'."
                )


def validate_station_codes(
    chem_df: pd.DataFrame,
    flow_df: pd.DataFrame,
):

    chem_stations = set(chem_df["station_code"].astype(str).unique())

    flow_stations = set(flow_df["station_code"].astype(str).unique())

    missing_flow = chem_stations - flow_stations
    missing_chem = flow_stations - chem_stations

    if missing_flow:

        raise ValidationError(
            f"Missing flow data for stations: " f"{sorted(missing_flow)}"
        )

    if missing_chem:

        raise ValidationError(
            f"Missing chemistry data for stations: " f"{sorted(missing_chem)}"
        )


def validate_workbook(
    chem_df: pd.DataFrame,
    flow_df: pd.DataFrame,
) -> Dict:

    parameter_columns = validate_chem_sheet(chem_df)

    validate_flow_sheet(flow_df)

    chem_df, flow_df = validate_dates(
        chem_df,
        flow_df,
    )

    validate_concentrations(
        chem_df,
        parameter_columns,
    )

    validate_station_codes(
        chem_df,
        flow_df,
    )

    return {
        "parameter_columns": parameter_columns,
        "parameter_info": get_parameter_info(chem_df),
        "stations": sorted(chem_df["station_code"].unique()),
        "n_stations": chem_df["station_code"].nunique(),
    }