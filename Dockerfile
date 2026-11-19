FROM python:3.13

WORKDIR /app

# ------------------------------------------------------------------
# System dependencies + R
# ------------------------------------------------------------------

RUN apt-get update && apt-get install -y \
    r-base \
    r-base-dev \
    build-essential \
    gfortran \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    libfontconfig1-dev \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# Python dependencies
# ------------------------------------------------------------------

COPY requirements.txt .

RUN pip install --no-cache-dir \
    -r requirements.txt

# ------------------------------------------------------------------
# R dependencies
# ------------------------------------------------------------------

RUN Rscript -e "install.packages( \
    c( \
        'EGRET', \
        'dplyr', \
        'readr', \
        'lubridate' \
    ), \
    repos='https://cloud.r-project.org' \
)"

# ------------------------------------------------------------------
# Application files
# ------------------------------------------------------------------

COPY . .

# ------------------------------------------------------------------
# Runtime directories
# ------------------------------------------------------------------
RUN mkdir -p /tmp

# ------------------------------------------------------------------
# Streamlit
# ------------------------------------------------------------------

EXPOSE 8501

CMD ["streamlit", "run", "app/Home.py", "--server.port=8501", "--server.address=0.0.0.0", "--browser.gatherUsageStats=false"]