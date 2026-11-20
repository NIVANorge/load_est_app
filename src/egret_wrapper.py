from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from src import config
from src.results import load_annual_results, load_flow_normalised_results
from src.utils import (
    create_egret_daily_frame,
    create_egret_sample_frame,
    find_parameter_columns,
)


class EgretError(Exception):
    pass


# ---------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------
def create_job_dir() -> Path:

    jobs_dir = Path(config.TMP_DIR) / "jobs"

    jobs_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    job_id = uuid.uuid4().hex[:12]

    job_dir = jobs_dir / f"job_{job_id}"

    job_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    return job_dir


def cleanup_job_dir(
    job_dir: Path,
):

    if job_dir.exists():

        shutil.rmtree(
            job_dir,
            ignore_errors=True,
        )


def cleanup_all_job_dirs() -> None:
    """
    Delete all EGRET job directories.

    Useful when a new workbook is uploaded or
    when the file uploader is cleared.
    """

    jobs_dir = Path(config.TMP_DIR) / "jobs"

    if not jobs_dir.exists():
        return

    for path in jobs_dir.iterdir():

        if path.is_dir():

            shutil.rmtree(
                path,
                ignore_errors=True,
            )


# ---------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------
def list_job_files(
    job_dir: Path,
) -> list[str]:

    files = []

    for p in sorted(job_dir.rglob("*")):

        if p.is_file():

            files.append(str(p.relative_to(job_dir)))

    return files


# ---------------------------------------------------------------------
# Input generation
# ---------------------------------------------------------------------
def write_model_inputs(
    chem_df: pd.DataFrame,
    flow_df: pd.DataFrame,
    job_dir: Path,
) -> tuple[int, list[str], pd.DataFrame]:

    all_warnings = []
    plot_frames = []

    parameter_columns = find_parameter_columns(chem_df)

    model_count = 0

    stations = sorted(chem_df["station_code"].unique())

    for station in stations:

        chem_station = chem_df[chem_df["station_code"] == station].copy()

        flow_station = flow_df[flow_df["station_code"] == station].copy()

        daily_full, flow_warnings = create_egret_daily_frame(flow_station)

        all_warnings.extend([f"{station}: {msg}" for msg in flow_warnings])

        flow_start = pd.to_datetime(daily_full["Date"]).min()

        flow_end = pd.to_datetime(daily_full["Date"]).max()

        for parameter_column in parameter_columns:

            sample, sample_warnings = create_egret_sample_frame(
                chem_station,
                parameter_column,
            )

            if sample.empty:
                continue

            parameter = sample.attrs["parameter"]

            all_warnings.extend(
                [f"{station} {parameter}: {msg}" for msg in sample_warnings]
            )

            sample_dates = pd.to_datetime(sample["Date"])

            chem_start = sample_dates.min()

            chem_end = sample_dates.max()

            overlap_start = max(
                chem_start,
                flow_start,
            )

            overlap_end = min(
                chem_end,
                flow_end,
            )

            start_year = overlap_start.year

            end_year = overlap_end.year

            common_start = pd.Timestamp(
                start_year,
                1,
                1,
            )

            common_end = pd.Timestamp(
                end_year,
                12,
                31,
            )

            sample = sample[
                pd.to_datetime(sample["Date"]).between(
                    common_start,
                    common_end,
                )
            ].copy()

            if sample.empty:
                continue

            daily = daily_full[
                pd.to_datetime(daily_full["Date"]).between(
                    common_start,
                    common_end,
                )
            ].copy()

            if daily.empty:
                continue

            # ----------------------------------------------------------
            # Save plot data
            # ----------------------------------------------------------
            flow_plot = pd.DataFrame(
                {
                    "station_code": station,
                    "parameter": parameter,
                    "date": pd.to_datetime(daily["Date"]),
                    "flow": daily["Q"],
                    "concentration": np.nan,
                    "series": "flow",
                }
            )

            sample_plot = pd.DataFrame(
                {
                    "station_code": station,
                    "parameter": parameter,
                    "date": pd.to_datetime(sample["Date"]),
                    "flow": np.nan,
                    "concentration": sample["Value"],
                    "series": "sample",
                }
            )

            plot_frames.extend(
                [
                    flow_plot,
                    sample_plot,
                ]
            )

            # ----------------------------------------------------------
            # Write EGRET inputs
            # ----------------------------------------------------------
            model_dir = job_dir / f"{station}__{parameter}"

            model_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            sample.to_csv(
                model_dir / "sample.csv",
                index=False,
            )

            daily.to_csv(
                model_dir / "daily.csv",
                index=False,
            )

            model_count += 1

    cleaned_inputs = (
        pd.concat(
            plot_frames,
            ignore_index=True,
        )
        if plot_frames
        else pd.DataFrame(
            columns=[
                "station_code",
                "parameter",
                "date",
                "flow",
                "concentration",
                "series",
            ]
        )
    )

    return (
        model_count,
        all_warnings,
        cleaned_inputs,
    )


# ---------------------------------------------------------------------
# R execution
# ---------------------------------------------------------------------
def build_command(
    job_dir: Path,
):

    return [
        "Rscript",
        config.R_SCRIPT_PATH,
        str(job_dir),
    ]


def stream_r_process(
    job_dir: Path,
):

    proc = subprocess.Popen(
        build_command(job_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    try:

        while True:

            line = proc.stdout.readline()

            if line == "" and proc.poll() is not None:
                break

            if line:

                yield line.rstrip()

        return_code = proc.wait()

        if return_code != 0:

            raise EgretError(f"Rscript returned " f"{return_code}")

    except Exception:

        proc.kill()

        raise


# ---------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------
def load_outputs(
    job_dir: Path,
):

    annual_csv = job_dir / "annual_loads.csv"

    fn_csv = job_dir / "flow_normalised_loads.csv"

    diagnostics_csv = job_dir / "diagnostics.csv"

    if not annual_csv.exists():

        raise EgretError("Missing annual_loads.csv")

    if not fn_csv.exists():

        raise EgretError("Missing flow_normalised_loads.csv")

    annual_df = load_annual_results(annual_csv)

    fn_df = load_flow_normalised_results(fn_csv)

    diagnostics_df = (
        pd.read_csv(diagnostics_csv) if diagnostics_csv.exists() else pd.DataFrame()
    )

    if annual_df.empty and fn_df.empty:

        if not diagnostics_df.empty:

            error_rows = diagnostics_df[diagnostics_df["status"] == "ERROR"]

            if not error_rows.empty:

                messages = error_rows["message"].dropna().astype(str).unique().tolist()

                raise EgretError("All EGRET models failed:\n" + "\n".join(messages))

        raise EgretError("EGRET produced no load estimates.")

    return (
        annual_df,
        fn_df,
        diagnostics_df,
    )


# ---------------------------------------------------------------------
# Main job
# ---------------------------------------------------------------------
class EgretJob:

    def __init__(
        self,
        chem_df,
        flow_df,
    ):

        self.chem_df = chem_df
        self.flow_df = flow_df

        self.job_dir = None

    def prepare(
        self,
    ):

        self.job_dir = create_job_dir()

        n = write_model_inputs(
            self.chem_df,
            self.flow_df,
            self.job_dir,
        )

        if n == 0:

            raise EgretError("No EGRET models created.")

        return n

    def run(self):

        for msg in stream_r_process(self.job_dir):
            yield msg

    def load_results(
        self,
    ):
        return load_outputs(self.job_dir)


def run_egret(
    job_dir: Path,
):

    for msg in stream_r_process(job_dir):
        yield msg