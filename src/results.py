from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import pymannkendall as mk
from src.utils import annual_load_column, flow_normalised_load_column


# -----------------------------------------------------------------------------
# Loading EGRET outputs
# -----------------------------------------------------------------------------
def load_annual_results(
    csv_path: str | Path,
) -> pd.DataFrame:
    """
    Load annual results produced by EGRET.

    Required columns:

        station_code
        parameter
        year
        tonnes
    """

    df = pd.read_csv(csv_path)

    required = {
        "station_code",
        "parameter",
        "year",
        "tonnes",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing columns in annual " f"results: {sorted(missing)}")

    return df


def load_flow_normalised_results(
    csv_path: str | Path,
) -> pd.DataFrame:
    """
    Load flow-normalised results produced by EGRET.

    Required columns:

        station_code
        parameter
        year
        tonnes
    """

    df = pd.read_csv(csv_path)

    required = {
        "station_code",
        "parameter",
        "year",
        "tonnes",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns in flow-normalised " f"results: {sorted(missing)}"
        )

    return df


# -----------------------------------------------------------------------------
# Pivot helpers
# -----------------------------------------------------------------------------
def annual_results_wide(
    annual_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert annual loads to wide format.

    Input

        station_code
        parameter
        year
        tonnes

    Output

        station_code
        year
        TN_tonnes
        TP_tonnes
        ...
    """

    df = annual_df.copy()

    df["column"] = df["parameter"].apply(annual_load_column)

    wide = df.pivot_table(
        index=[
            "station_code",
            "year",
        ],
        columns="column",
        values="tonnes",
        aggfunc="first",
    ).reset_index()

    wide.columns.name = None

    return wide


def flow_normalised_results_wide(
    fn_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert FN results to wide format.

    Output

        station_code
        year
        FN_TN_tonnes
        FN_TP_tonnes
    """

    df = fn_df.copy()

    df["column"] = df["parameter"].apply(flow_normalised_load_column)

    wide = df.pivot_table(
        index=[
            "station_code",
            "year",
        ],
        columns="column",
        values="tonnes",
        aggfunc="first",
    ).reset_index()

    wide.columns.name = None

    return wide


# -----------------------------------------------------------------------------
# Merging annual + FN results
# -----------------------------------------------------------------------------
def merge_load_results(
    annual_df: pd.DataFrame,
    fn_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create final output table.

    Example

        station_code
        year
        TN_tonnes
        FN_TN_tonnes
        TP_tonnes
        FN_TP_tonnes
    """

    annual_wide = annual_results_wide(annual_df)

    fn_wide = flow_normalised_results_wide(fn_df)

    result = annual_wide.merge(
        fn_wide,
        on=[
            "station_code",
            "year",
        ],
        how="outer",
    )

    result = result.sort_values(
        [
            "station_code",
            "year",
        ]
    )

    return result.reset_index(drop=True)


# -----------------------------------------------------------------------------
# Diagnostics
# -----------------------------------------------------------------------------
def load_diagnostics(
    csv_path: str | Path,
) -> pd.DataFrame:
    """
    Load diagnostics produced by run_egret.R.
    """

    df = pd.read_csv(csv_path)

    required = {
        "station_code",
        "parameter",
        "status",
        "message",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing columns in diagnostics: {sorted(missing)}")

    return df


# -----------------------------------------------------------------------------
# Excel export
# -----------------------------------------------------------------------------
def workbook_bytes(
    annual_df: pd.DataFrame,
    fn_df: pd.DataFrame,
    diagnostics_df: pd.DataFrame,
) -> bytes:
    """
    Produce workbook bytes suitable for
    Streamlit download_button().
    """

    buffer = BytesIO()

    combined = merge_load_results(
        annual_df,
        fn_df,
    )

    annual_trends = calculate_trends(annual_df)

    fn_trends = calculate_trends(fn_df)

    annual_trends["series"] = "Annual"

    fn_trends["series"] = "Flow-normalised"

    annual_trends = annual_trends[
        [
            "station_code",
            "parameter",
            "series",
            "mk_trend",
            "mk_pval",
            "sens_slope_tonnes-per-year",
            # "sens_intercept",
        ]
    ]

    fn_trends = fn_trends[
        [
            "station_code",
            "parameter",
            "series",
            "mk_trend",
            "mk_pval",
            "sens_slope_tonnes-per-year",
            # "sens_intercept",
        ]
    ]

    trends = pd.concat(
        [
            annual_trends,
            fn_trends,
        ],
        ignore_index=True,
    )

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl",
    ) as writer:

        combined.to_excel(
            writer,
            sheet_name="loads",
            index=False,
        )

        trends.to_excel(
            writer,
            sheet_name="trends",
            index=False,
        )

        diagnostics_df.to_excel(
            writer,
            sheet_name="diagnostics",
            index=False,
        )

    buffer.seek(0)

    return buffer.getvalue()


def calculate_trends(
    df: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for (
        station_code,
        parameter,
    ), grp in df.groupby(
        [
            "station_code",
            "parameter",
        ]
    ):

        grp = grp.sort_values("year")

        y = grp["tonnes"].to_numpy()

        x = grp["year"].to_numpy()

        if len(y) < 3:
            continue

        result = mk.original_test(y)

        slope = result.slope

        intercept = np.median(y - slope * x)

        rows.append(
            {
                "station_code": station_code,
                "parameter": parameter,
                "mk_trend": result.trend.capitalize(),
                "mk_pval": result.p,
                "sens_slope_tonnes-per-year": slope,
                "sens_intercept": intercept,
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:

        return pd.DataFrame(
            columns=[
                "station_code",
                "parameter",
                "mk_trend",
                "mk_pval",
                "sens_slope_tonnes-per-year",
                "sens_intercept",
            ]
        )

    return df