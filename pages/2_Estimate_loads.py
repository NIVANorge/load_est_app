from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from src import config
from src.egret_wrapper import (
    cleanup_all_job_dirs,
    cleanup_job_dir,
    create_job_dir,
    load_outputs,
    stream_r_process,
    write_model_inputs,
)
from src.results import calculate_trends, workbook_bytes
from src.utils import check_date_overlap
from src.validation import ValidationError, validate_workbook

st.set_page_config(page_icon="📈")
st.title("Estimate loads")

# ---------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------
uploaded_file = st.file_uploader(
    "Upload completed Excel template",
    type=["xlsx"],
)

if uploaded_file is None:

    cleanup_all_job_dirs()

    for key in [
        "uploaded_file_id",
        "job_dir",
        "model_count",
        "annual_df",
        "fn_df",
        "diag_df",
    ]:
        st.session_state.pop(key, None)

    st.stop()

# Detect a newly uploaded file
file_id = (
    uploaded_file.name,
    uploaded_file.size,
)

if st.session_state.get("uploaded_file_id") != file_id:
    # New file uploaded -> clear previous results
    cleanup_all_job_dirs()

    for key in [
        "job_dir",
        "model_count",
        "annual_df",
        "fn_df",
        "diag_df",
    ]:
        st.session_state.pop(key, None)

    st.session_state["uploaded_file_id"] = file_id

# ---------------------------------------------------------------------
# Read workbook
# ---------------------------------------------------------------------
try:

    chem_df = pd.read_excel(
        uploaded_file,
        sheet_name=config.CHEM_SHEET,
    )

    flow_df = pd.read_excel(
        uploaded_file,
        sheet_name=config.FLOW_SHEET,
    )

except Exception as e:

    st.error(f"Failed to read workbook: {e}")

    st.stop()

# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------
try:

    metadata = validate_workbook(
        chem_df,
        flow_df,
    )

except ValidationError as e:

    st.error(str(e))

    st.stop()

except Exception as e:

    st.error(f"Unexpected validation error: {e}")

    st.stop()

# ---------------------------------------------------------------------
# Date trimming
# ---------------------------------------------------------------------
try:

    warnings = check_date_overlap(chem_df, flow_df)

except Exception as e:

    st.error(f"Failed preparing data: {e}")

    st.stop()

for warning in warnings:

    st.warning(f"{warning['station_code']}: " f"{warning['message']}")

st.success("Workbook validation passed.")

# ---------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "Stations",
        metadata["n_stations"],
    )

with col2:

    st.metric(
        "Parameters",
        len(metadata["parameter_columns"]),
    )

with col3:

    st.metric(
        "Chemistry samples",
        len(chem_df),
    )

# ---------------------------------------------------------------------
# Stations and parameters
# ---------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:

    st.subheader("Stations")

    station_df = pd.DataFrame({"station_code": metadata["stations"]})

    st.dataframe(
        station_df,
        width="content",
        hide_index=True,
    )

with col2:

    st.subheader("Parameters")

    st.dataframe(
        metadata["parameter_info"],
        width="content",
        hide_index=True,
    )

# ---------------------------------------------------------------------
# Station-Parameter Summary
# ---------------------------------------------------------------------
st.subheader("Station-parameter summary")

rows = []

for station in metadata["stations"]:

    chem_station = chem_df[chem_df["station_code"] == station].copy()

    flow_station = flow_df[flow_df["station_code"] == station].copy()

    flow_station["date"] = pd.to_datetime(flow_station["date"])

    flow_start = flow_station["date"].min()
    flow_end = flow_station["date"].max()

    for parameter_column in metadata["parameter_columns"]:

        samples = chem_station[
            [
                "date",
                parameter_column,
            ]
        ].copy()

        samples = samples[samples[parameter_column].notna()]

        if samples.empty:
            continue

        samples["date"] = pd.to_datetime(samples["date"])

        chem_start = samples["date"].min()

        chem_end = samples["date"].max()

        overlap_start = max(chem_start, flow_start)

        overlap_end = min(chem_end, flow_end)

        model_start = pd.Timestamp(overlap_start.year, 1, 1)

        model_end = pd.Timestamp(overlap_end.year, 12, 31)

        samples_trimmed = samples[
            samples["date"].between(
                overlap_start,
                overlap_end,
            )
        ]

        flow_trimmed = flow_station[
            flow_station["date"].between(
                overlap_start,
                overlap_end,
            )
        ]

        if samples_trimmed.empty:
            continue

        rows.append(
            {
                "station_code": station,
                "parameter": parameter_column,
                "n_chem_samples": len(samples_trimmed),
                "n_flow_samples": len(flow_trimmed),
                "model_start": model_start,
                "model_end": model_end,
            }
        )

station_summary = pd.DataFrame(rows)

if not station_summary.empty:

    station_summary = station_summary.sort_values(
        [
            "station_code",
            "parameter",
        ]
    ).reset_index(drop=True)

    station_summary["model_start"] = pd.to_datetime(
        station_summary["model_start"]
    ).dt.date

    station_summary["model_end"] = pd.to_datetime(station_summary["model_end"]).dt.date

n_combos = len(station_summary)
st.markdown(
    f"EGRET will fit WRTDS models for the following **{n_combos} "
    f"station-parameter combinations**. Expect processing to take "
    f"up to **{n_combos} minutes**."
)

st.dataframe(
    station_summary,
    width="content",
    hide_index=True,
)


# ---------------------------------------------------------------------
# EGRET inputs
# ---------------------------------------------------------------------
st.divider()

st.subheader("Generate EGRET inputs")

st.markdown(
    """
    Click the button below to generate EGRET input files for each station-parameter combination
    in your data.
    """
)

if st.button(
    "Generate EGRET inputs",
    type="primary",
):

    try:

        job_dir = create_job_dir()

        model_count, data_warnings = write_model_inputs(chem_df, flow_df, job_dir)

        st.session_state["model_count"] = model_count

        for warning in data_warnings:

            st.warning(warning)

        st.session_state["job_dir"] = str(job_dir)

        st.success(f"Created {model_count} EGRET models.")

    except Exception as e:

        st.error(f"Failed creating EGRET inputs: {e}")

if "job_dir" in st.session_state:

    st.success("Inputs created successfully.")


# ---------------------------------------------------------------------
# Run EGRET
# ---------------------------------------------------------------------
st.divider()

st.subheader("Run EGRET")

st.markdown(
    """
    Click the button below to fit WRTDS models using EGRET.
    """
)

if "job_dir" in st.session_state:

    job_dir = Path(st.session_state["job_dir"])

    if st.button("Run EGRET", type="primary"):

        try:

            messages = []

            with st.expander("Show log", expanded=False):

                log_container = st.empty()

                for line in stream_r_process(job_dir):

                    messages.append(line)

                    log_container.code("\n".join(messages))

            annual_df, fn_df, diag_df = load_outputs(job_dir)

            cleanup_job_dir(job_dir)

            st.session_state.pop("job_dir", None)

            model_count = int(st.session_state["model_count"])
            n_ok = int((diag_df["status"] == "OK").sum())
            n_error = model_count - n_ok

            if n_error == 0:
                st.success(f"All {model_count} EGRET model(s) completed successfully.")

            else:
                st.warning(
                    f"{n_error} of {model_count} EGRET model(s) failed. "
                    f"Check the log above for details."
                )

            st.session_state["annual_df"] = annual_df

            st.session_state["fn_df"] = fn_df

            st.session_state["diag_df"] = diag_df

        except Exception as e:

            cleanup_job_dir(job_dir)

            st.session_state.pop("job_dir", None)

            st.error(f"EGRET failed: {e}")

# ---------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------
if "annual_df" in st.session_state:

    annual_df = st.session_state["annual_df"]

    fn_df = st.session_state["fn_df"]

    diag_df = st.session_state["diag_df"]

    annual_trends = calculate_trends(annual_df)

    if not annual_trends.empty:

        annual_trends["series"] = "Annual"

    fn_trends = calculate_trends(fn_df)

    if not fn_trends.empty:

        fn_trends["series"] = "Flow-normalised"

    trend_frames = []

    if not annual_trends.empty:

        trend_frames.append(annual_trends)

    if not fn_trends.empty:

        trend_frames.append(fn_trends)

    if trend_frames:

        trends = pd.concat(
            trend_frames,
            ignore_index=True,
        )

    else:

        trends = pd.DataFrame()

    xlsx_bytes = workbook_bytes(
        annual_df,
        fn_df,
        diag_df,
    )

    st.download_button(
        label="⬇️ Download Results Workbook",
        data=xlsx_bytes,
        file_name="load_estimates.xlsx",
        mime=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        width="content",
    )

    # ---------------------------------------------------------------------
    # Visualisation
    # ---------------------------------------------------------------------
    st.divider()

    st.subheader("Visualisation")

    st.markdown(
        """
        The upper plot shows **annual loads** and the lower plot shows **flow-normalised loads**.
        Flow normalisation removes the effects of year-to-year weather and streamflow variability,
        thereby emphasising underlying water-quality patterns.
        
        Trends are indicated by fitted **Sen's slope** lines. Solid red lines show statistically 
        significant trends (Mann-Kendall *p* ≤ 0.05); dashed red lines indicate trend tendencies 
        (0.05 < *p* ≤ 0.10); and dashed black lines indicate non-significant trends (*p* > 0.10).
        """
    )

    col1, col2 = st.columns(2)

    with col1:
        stations = sorted(annual_df["station_code"].unique())
        station = st.selectbox("Station", stations)

    with col2:
        parameters = sorted(
            annual_df.loc[
                annual_df["station_code"] == station,
                "parameter",
            ].unique()
        )
        parameter = st.selectbox("Parameter", parameters)

    annual_plot = annual_df[
        (annual_df["station_code"] == station) & (annual_df["parameter"] == parameter)
    ].copy()

    if trends.empty:

        annual_trend = pd.DataFrame()

    else:

        annual_trend = trends[
            (trends["station_code"] == station)
            & (trends["parameter"] == parameter)
            & (trends["series"] == "Annual")
        ]

    fn_plot = fn_df[
        (fn_df["station_code"] == station) & (fn_df["parameter"] == parameter)
    ].copy()

    if trends.empty:

        fn_trend = pd.DataFrame()

    else:

        fn_trend = trends[
            (trends["station_code"] == station)
            & (trends["parameter"] == parameter)
            & (trends["series"] == "Flow-normalised")
        ]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        shared_yaxes=True,
        vertical_spacing=0.08,
    )

    # ----------------------------------------------------------
    # Annual loads
    # ----------------------------------------------------------
    fig.add_trace(
        go.Scatter(
            x=annual_plot["year"],
            y=annual_plot["tonnes"],
            mode="lines+markers",
            name="Annual Load",
            line=dict(
                color="#1b9e77",
                width=3,
            ),
            marker=dict(
                size=10,
            ),
            hovertemplate=(
                "<b>Year</b>: %{x}"
                "<br>"
                "<b>Annual Load</b>: %{y:,.1f} tonnes"
                "<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    if not annual_trend.empty:

        slope = annual_trend["sens_slope_tonnes-per-year"].iloc[0]

        intercept = annual_trend["sens_intercept"].iloc[0]

        p = annual_trend["mk_pval"].iloc[0]

        years = annual_plot["year"]

        trend_line = intercept + slope * years

        if p <= 0.05:

            color = "red"
            width = 2
            dash = "solid"

        elif p <= 0.10:

            color = "red"
            width = 2
            dash = "dash"

        else:

            color = "black"
            width = 2
            dash = "dash"

        fig.add_trace(
            go.Scatter(
                x=years,
                y=trend_line,
                mode="lines",
                name="Annual Trend",
                line=dict(
                    color=color,
                    width=width,
                    dash=dash,
                ),
            ),
            row=1,
            col=1,
        )

    # ----------------------------------------------------------
    # Flow-normalised loads
    # ----------------------------------------------------------
    fig.add_trace(
        go.Scatter(
            x=fn_plot["year"],
            y=fn_plot["tonnes"],
            mode="lines+markers",
            name="Flow-Normalised Load",
            line=dict(
                color="#7570b3",
                width=3,
            ),
            marker=dict(
                size=10,
            ),
            hovertemplate=(
                "<b>Year</b>: %{x}"
                "<br>"
                "<b>Flow-Normalised Load</b>: %{y:,.1f} tonnes"
                "<extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    if not fn_trend.empty:

        slope = fn_trend["sens_slope_tonnes-per-year"].iloc[0]

        intercept = fn_trend["sens_intercept"].iloc[0]

        p = fn_trend["mk_pval"].iloc[0]

        years = fn_plot["year"]

        trend_line = intercept + slope * years

        if p <= 0.05:

            color = "red"
            width = 2
            dash = "solid"

        elif p <= 0.10:

            color = "red"
            width = 2
            dash = "dash"

        else:

            color = "black"
            width = 2
            dash = "dash"

        fig.add_trace(
            go.Scatter(
                x=years,
                y=trend_line,
                mode="lines",
                name="FN Trend",
                line=dict(
                    color=color,
                    width=width,
                    dash=dash,
                ),
            ),
            row=2,
            col=1,
        )

    # ----------------------------------------------------------
    # Shared y-axis scale
    # ----------------------------------------------------------
    ymax = max(
        annual_plot["tonnes"].max(),
        fn_plot["tonnes"].max(),
    )

    fig.update_yaxes(
        range=[
            0,
            ymax * 1.05,
        ]
    )

    # ----------------------------------------------------------
    # Axis labels
    # ----------------------------------------------------------
    fig.update_yaxes(
        title_text="Load (tonnes)",
        title_font=dict(size=18),
        tickfont=dict(size=14),
        row=1,
        col=1,
    )

    fig.update_yaxes(
        title_text="Load (tonnes)",
        title_font=dict(size=18),
        tickfont=dict(size=14),
        row=2,
        col=1,
    )

    # ----------------------------------------------------------
    # Styling
    # ----------------------------------------------------------
    fig.update_layout(
        template="ggplot2",
        height=700,
        hovermode="x unified",
        title=dict(
            text=f"{station} | {parameter}",
            x=0.5,
            font=dict(
                size=24,
            ),
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="middle",
            y=0.5,
            xanchor="center",
            x=0.5,
            font=dict(
                size=16,
            ),
        ),
        font=dict(
            size=16,
        ),
        plot_bgcolor="#EBEBEB",
        paper_bgcolor="white",
        margin=dict(
            l=70,
            r=25,
            t=70,
            b=40,
        ),
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="white",
        zeroline=False,
        title_font=dict(size=18),
        tickfont=dict(size=14),
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="white",
        zeroline=True,
        zerolinecolor="white",
    )

    st.plotly_chart(
        fig,
        width="stretch",
    )

    # ---------------------------------------------------------------------
    # Trend Summary
    # ---------------------------------------------------------------------
    st.subheader("Trends")

    if trends.empty:

        st.info("No trend results available.")

    else:

        trend_summary = trends[
            (trends["station_code"] == station) & (trends["parameter"] == parameter)
        ].copy()

        if trend_summary.empty:

            st.info("No trend results available.")

        else:

            trend_summary = trend_summary[
                [
                    "series",
                    "mk_trend",
                    "mk_pval",
                    "sens_slope_tonnes-per-year",
                ]
            ]
            trend_summary["mk_pval"] = trend_summary["mk_pval"].round(3)
            trend_summary["sens_slope_tonnes-per-year"] = trend_summary[
                "sens_slope_tonnes-per-year"
            ].round(2)

            st.dataframe(
                trend_summary,
                width="content",
                hide_index=True,
            )

    # ---------------------------------------------------------------------
    # WRTDS Summary
    # ---------------------------------------------------------------------
    st.subheader("Summary")

    diag_row = diag_df[
        (diag_df["station_code"] == station) & (diag_df["parameter"] == parameter)
    ]

    if not diag_row.empty:

        d = diag_row.iloc[0]

        flux_change_pct = float(d["flux_change_pct"])
        flux_qtc_pct = float(d["flux_qtc_pct"])
        flux_cqtc_pct = float(d["flux_cqtc_pct"])

        year_start = int(d["year_start"])
        year_end = int(d["year_end"])

        annual_row = trend_summary[trend_summary["series"] == "Annual"]

        fn_row = trend_summary[trend_summary["series"] == "Flow-normalised"]

        def significance_text(p):

            if pd.isna(p):
                return "of unknown significance"

            if p <= 0.05:
                return f"**statistically significant** (Mann-Kendall *p* = {p:.3f})"

            if p <= 0.10:
                return f"**marginally statistically significant** (Mann-Kendall *p* = {p:.3f})"

            return f"**not statistically significant** (Mann-Kendall *p* = {p:.3f})"

        annual_sig = (
            significance_text(float(annual_row.iloc[0]["mk_pval"]))
            if not annual_row.empty
            else "of unknown significance"
        )

        fn_sig = (
            significance_text(float(fn_row.iloc[0]["mk_pval"]))
            if not fn_row.empty
            else "of unknown significance"
        )

        direction = "increased" if flux_change_pct >= 0 else "decreased"

        st.markdown(
            f"""
            **{parameter}** at **{station}** has **{direction}** 
            by **{abs(flux_change_pct):.1f} %**
            between **{year_start}** and **{year_end}**.
            
             * Changes in runoff/streamflow contributed **{flux_qtc_pct:+.1f} percentage points**.
             * Changes in water quality independent of streamflow contributed
              **{flux_cqtc_pct:+.1f} percentage points**.
             * The trend in **annual** loads is {annual_sig}.
             * The trend in **flow-normalised** loads is {fn_sig}.
            """
        )

    # ---------------------------------------------------------------------
    # Model performance
    # ---------------------------------------------------------------------
    st.subheader("Model Performance")

    diag_row = diag_df[
        (diag_df["station_code"] == station) & (diag_df["parameter"] == parameter)
    ]

    if diag_row.empty:

        st.info("No diagnostics available.")

    else:

        d = diag_row.iloc[0]

        performance = pd.DataFrame(
            {
                "Metric": [
                    "Model start year",
                    "Model end year",
                    "Number of samples",
                    "Number censored",
                    "Percent censored",
                    "R² (log concentration)",
                    "RMSE (log concentration)",
                    "Mean log residual",
                    "Flux bias",
                    "Flux bias (low)",
                    "Flux bias (high)",
                    "Residual-flow correlation",
                    "Residual-time correlation",
                    "Quality",
                ],
                "Value": [
                    d["year_start"],
                    d["year_end"],
                    d["n_samples"],
                    d["n_censored"],
                    d["pct_censored"],
                    d["r2_log"],
                    d["rmse_log"],
                    d["mean_residual_log"],
                    d["flux_bias"],
                    d["flux_bias_low"],
                    d["flux_bias_high"],
                    d["corr_residual_flow"],
                    d["corr_residual_time"],
                    d["quality"],
                ],
                "Description": [
                    "First year included in analysis.",
                    "Last year included in analysis.",
                    "Chemistry samples used by WRTDS.",
                    "Samples treated as censored observations.",
                    "Percentage of censored observations.",
                    "Pseudo-R² for log concentrations.",
                    "Root-mean-square error for log concentrations.",
                    "Average log residual. Values near 0 are desirable.",
                    "Estimated load bias. Values near 0 are desirable.",
                    "Flux bias using upper censoring bound.",
                    "Flux bias using lower censoring bound.",
                    "Correlation between residuals and flow. Values near 0 are desirable.",
                    "Correlation between residuals and time. Values near zero are desirable.",
                    "Overall heuristic model quality assessment.",
                ],
            }
        )

        performance["Value"] = performance["Value"].astype(str)

        st.dataframe(
            performance,
            hide_index=True,
            width="stretch",
        )

        st.markdown(
            """
            For further details of the performance metircs, see 
            [here](https://github.com/NIVANorge/load_est_app/blob/main/docs/model_fit_metrics.md).
            """
        )