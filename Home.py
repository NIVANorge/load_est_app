from pathlib import Path

import streamlit as st
from src.config import APP_TITLE, TEMPLATE_PATH

st.set_page_config(page_icon="💧")
st.title(APP_TITLE)

st.markdown(
    """
    This app allows you to estimate **annual** and **flow-normalised annual** loads from your own
    data. Loads are calculated using **Weighted Regressions on Time, Discharge and Season (WRTDS)**
    using the R-Package [EGRET](https://doi-usgs.github.io/EGRET/).

    To begin, click the button below to download an Excel template where you can add your data. Then
    go to the `Estimate loads` page (left sidebar) to upload your Excel file and calculate loads. 
    Example data for testing can be downloaded [here](xxxxxx).
    """
)

st.warning(
    """
    **Note:** EGRET is designed for analysis of long-term monitoring series (preferably decades). You
    must upload **at least 100 samples** spanning several years.
    """
)

st.subheader("Download template")

with open(TEMPLATE_PATH, "rb") as f:

    st.download_button(
        label="⬇️ Download Excel template",
        data=f.read(),
        file_name="loads_app_input_template.xlsx",
        mime=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        width="content",
    )