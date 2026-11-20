FROM rocker/geospatial:latest

WORKDIR /app

# ------------------------------------------------------------------
# System dependencies
# ------------------------------------------------------------------
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    gfortran \
    cmake \
    pkg-config \
    libuv1-dev \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# Python environment
# ------------------------------------------------------------------
COPY requirements.txt .

RUN python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --upgrade pip

RUN pip install --no-cache-dir \
    -r requirements.txt

# ------------------------------------------------------------------
# R dependencies
# ------------------------------------------------------------------
COPY r_packages.R .

RUN Rscript r_packages.R

# ------------------------------------------------------------------
# Application files
# ------------------------------------------------------------------
COPY Home.py .
COPY templates/ ./templates/
COPY src/ ./src/
COPY r/ ./r/
COPY pages/ ./pages/

# ------------------------------------------------------------------
# Runtime directories
# ------------------------------------------------------------------
RUN mkdir -p /tmp

# ------------------------------------------------------------------
# Streamlit configuration
# ------------------------------------------------------------------
EXPOSE 8501

CMD ["streamlit", "run", "Home.py", "--server.port=8501", "--server.address=0.0.0.0", "--browser.gatherUsageStats=false"]