from __future__ import annotations

import re

import numpy as np
import pandas as pd
from src import config

PARAM_PATTERN = re.compile(r"^(.+)_(mg/l|ug/l|ng/l)$", re.IGNORECASE)


def normalize_unit(unit: str) -> str:
    """
    Convert unit variants to a canonical form.

    Examples
    --------
    μg/l -> ug/l
    µg/l -> ug/l
    UG/L -> ug/l
    Mg/L -> mg/l
    """
    return (
        str(unit)
        .strip()
        .lower()
        .replace("μ", "u")  # Greek mu
        .replace("µ", "u")  # Micro sign
    )


def check_date_overlap(
    chem_df: pd.DataFrame,
    flow_df: pd.DataFrame,
):

    warnings = []

    chem_df = chem_df.copy()
    flow_df = flow_df.copy()

    chem_df["date"] = pd.to_datetime(chem_df["date"])

    flow_df["date"] = pd.to_datetime(flow_df["date"])

    for station in sorted(chem_df["station_code"].unique()):

        chem_station = chem_df[chem_df["station_code"] == station]

        flow_station = flow_df[flow_df["station_code"] == station]

        chem_start = chem_station["date"].min()
        chem_end = chem_station["date"].max()

        flow_start = flow_station["date"].min()
        flow_end = flow_station["date"].max()

        if chem_start < flow_start or chem_end > flow_end:

            warnings.append(
                {
                    "station_code": station,
                    "message": "Chemistry and flow periods do not fully overlap. "
                    "Data will be trimmed during EGRET input generation.",
                }
            )

    return warnings


def split_parameter_column(
    column_name: str,
) -> tuple[str, str]:
    """
    Example:
        TOTN_ug/l
        TOTN_μg/l
        TOTN_µg/l
        TOTN_UG/L

    Returns:
        ("TOTN", "ug/l")
    """

    try:
        parameter, unit = column_name.rsplit("_", 1)
    except ValueError:
        raise ValueError(f"Invalid parameter column: '{column_name}'")

    unit = normalize_unit(unit)

    if not PARAM_PATTERN.match(f"{parameter}_{unit}"):
        raise ValueError(f"Invalid parameter column: '{column_name}'")

    return parameter, unit


def get_parameter_name(
    column_name: str,
) -> str:

    return split_parameter_column(column_name)[0]


def get_parameter_unit(
    column_name: str,
) -> str:

    return split_parameter_column(column_name)[1]


def find_parameter_columns(
    chem_df: pd.DataFrame,
) -> list[str]:
    """
    Return parameter columns from the
    chemistry worksheet.
    """

    excluded = set(config.CHEM_REQUIRED_COLUMNS)

    return [col for col in chem_df.columns if col not in excluded]


def get_parameter_info(
    chem_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Describe parameter columns.
    """

    rows = []

    for col in find_parameter_columns(chem_df):

        parameter, unit = split_parameter_column(col)

        rows.append(
            {
                "column": col,
                "parameter": parameter,
                "unit": unit,
            }
        )

    return pd.DataFrame(rows)


def convert_to_mg_l(
    value: float,
    unit: str,
) -> float:
    """
    Convert concentration to mg/L.
    """

    if pd.isna(value):
        return np.nan

    unit = normalize_unit(unit)

    factor = config.UNIT_TO_MG_L.get(unit)

    if factor is None:
        raise ValueError(f"Unsupported unit: '{unit}'")

    return float(value) * factor


def parse_concentration(
    value,
) -> tuple[float, str]:
    """
    Parse chemistry concentrations.

    Examples

        0.5
        <0.1
        >100

    Returns

        value, censor_flag
    """

    if pd.isna(value):

        return np.nan, ""

    text = str(value).strip()

    if text.startswith("<"):

        return (
            float(text[1:].strip()),
            "<",
        )

    if text.startswith(">"):

        return (
            float(text[1:].strip()),
            ">",
        )

    return (
        float(text),
        "",
    )


def create_egret_sample_frame(
    chem_df: pd.DataFrame,
    parameter_column: str,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Create EGRET sample table for readUserSample().

    Output columns

        Date
        remarkCode
        Value

    Duplicate samples on the same day are aggregated.

    Rules
    -----
    - If any uncensored values exist on a day, average only the
      uncensored values and return an uncensored result.
    - If all values are '<', average the values and return '<'.
    - If all values are '>', average the values and return '>'.
    - If a day contains both '<' and '>' but no uncensored values,
      the day is dropped.
    - Days with no valid concentration values are dropped.

    Returns
    -------
    sample_df
    warnings
    """

    warnings = []

    parameter = get_parameter_name(parameter_column)

    unit = get_parameter_unit(parameter_column)

    df = chem_df[
        [
            "date",
            parameter_column,
        ]
    ].copy()

    df = df[df[parameter_column].notna()]

    # Parse concentrations and convert units
    parsed_rows = []

    for _, row in df.iterrows():

        value, censor = parse_concentration(row[parameter_column])

        if pd.isna(value):
            continue

        value = convert_to_mg_l(
            value,
            unit,
        )

        parsed_rows.append(
            {
                "Date": pd.to_datetime(row["date"]).normalize(),
                "remarkCode": (censor if censor is not None else ""),
                "Value": value,
            }
        )

    if not parsed_rows:

        result = pd.DataFrame(
            columns=[
                "Date",
                "remarkCode",
                "Value",
            ]
        )

        result.attrs["parameter"] = parameter

        return result, warnings

    parsed_df = pd.DataFrame(parsed_rows)

    # Record duplicate-sample warning
    sample_count = len(parsed_df)

    daily_count = parsed_df["Date"].nunique()

    duplicates_collapsed = sample_count - daily_count

    duplicate_days = parsed_df.groupby("Date").size().gt(1).sum()

    if duplicates_collapsed > 0:

        warnings.append(
            f"{duplicate_days} dates contained duplicate concentration measurements. "
            f"{duplicates_collapsed} observations were combined by daily averaging."
        )

    # Aggregate to daily values
    daily_rows = []

    dropped_mixed_censor_days = 0

    for date, grp in parsed_df.groupby(
        "Date",
        sort=True,
    ):

        uncensored = grp[~grp["remarkCode"].isin(["<", ">"])]

        # At least one uncensored value:
        # average only uncensored observations
        if len(uncensored) > 0:

            value = uncensored["Value"].mean()

            remark = ""

        else:

            censor_codes = set(grp["remarkCode"])

            # All below detection/quantification limit
            if censor_codes == {"<"}:

                value = grp["Value"].mean()

                remark = "<"

            # All above upper reporting limit
            elif censor_codes == {">"}:

                value = grp["Value"].mean()

                remark = ">"

            # Mixture of < and >
            else:

                dropped_mixed_censor_days += 1
                continue

        if pd.isna(value):
            continue

        daily_rows.append(
            {
                "Date": date.strftime("%Y-%m-%d"),
                "remarkCode": remark,
                "Value": value,
            }
        )

    if dropped_mixed_censor_days > 0:

        warnings.append(
            f"{dropped_mixed_censor_days} dates were dropped "
            f"because they contained a mixture of '<' and '>' "
            f"results with no uncensored observations."
        )

    result = pd.DataFrame(daily_rows)

    if not result.empty:

        result = result.sort_values("Date").reset_index(drop=True)

    result.attrs["parameter"] = parameter

    return result, warnings


def create_egret_daily_frame(
    flow_df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Create EGRET Daily table.

    Output columns

        Date
        Q

    Flow is resampled to daily means.
    Internal gaps are linearly interpolated.
    No extrapolation is performed.

    Returns
    -------
    daily_df
    warnings
    """

    warnings = []

    df = flow_df.copy()

    df["date"] = pd.to_datetime(df["date"])

    df["flow_m3/s"] = pd.to_numeric(df["flow_m3/s"], errors="coerce")

    if df["flow_m3/s"].isna().any():

        raise ValueError("Flow data contains non-numeric values.")

    df = df[["date", "flow_m3/s"]]

    df = df.set_index("date").sort_index().resample("D").mean()

    n_missing_before = int(df["flow_m3/s"].isna().sum())

    if n_missing_before > 0:

        df["flow_m3/s"] = df["flow_m3/s"].interpolate(
            method="linear", limit_area="inside"
        )

        n_missing_after_interp = int(df["flow_m3/s"].isna().sum())

        n_filled = n_missing_before - n_missing_after_interp

        if n_filled > 0:

            warnings.append(
                f"{n_filled} daily flow values filled by linear interpolation."
            )

    n_missing_after = int(df["flow_m3/s"].isna().sum())

    if n_missing_after > 0:

        raise ValueError(
            f"Flow record contains {n_missing_after} missing daily values "
            f"after interpolation. Leading/trailing gaps cannot be filled."
        )

    result = pd.DataFrame(
        {
            "Date": df.index.strftime("%Y-%m-%d"),
            "Q": df["flow_m3/s"],
        }
    )

    return (result.reset_index(drop=True), warnings)


def annual_load_column(
    parameter: str,
) -> str:

    return f"{parameter}{config.LOAD_SUFFIX}"


def flow_normalised_load_column(
    parameter: str,
) -> str:

    return f"{config.FLOW_NORMALISED_PREFIX}{parameter}{config.LOAD_SUFFIX}"