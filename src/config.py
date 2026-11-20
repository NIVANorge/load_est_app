from pathlib import Path

# -----------------------------------------------------------------------------
# Project paths
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
TMP_DIR = PROJECT_ROOT / "tmp"
TEMPLATE_PATH = TEMPLATES_DIR / "loads_app_input_template.xlsx"
TMP_DIR.mkdir(exist_ok=True)

# -----------------------------------------------------------------------------
# Excel sheets
# -----------------------------------------------------------------------------
CHEM_SHEET = "chem"
FLOW_SHEET = "flow"

# -----------------------------------------------------------------------------
# Required columns
# -----------------------------------------------------------------------------
CHEM_REQUIRED_COLUMNS = [
    "station_code",
    "station_name",
    "date",
]

FLOW_REQUIRED_COLUMNS = [
    "station_code",
    "date",
    "flow_m3/s",
]

# -----------------------------------------------------------------------------
# Parameter units
# -----------------------------------------------------------------------------
# Conversion factors to mg/L
# value_mg_l = value * UNIT_TO_MG_L[unit]
UNIT_TO_MG_L = {
    "mg/l": 1.0,
    "ug/l": 1e-3,
    "ng/l": 1e-6,
}

# -----------------------------------------------------------------------------
# EGRET configuration
# -----------------------------------------------------------------------------
R_SCRIPT_PATH = "r/run_egret.R"

# -----------------------------------------------------------------------------
# Streamlit
# -----------------------------------------------------------------------------
APP_TITLE = "River Load Estimation"

# -----------------------------------------------------------------------------
# Result column naming
# -----------------------------------------------------------------------------
LOAD_SUFFIX = "_tonnes"
FLOW_NORMALISED_PREFIX = "FN_"