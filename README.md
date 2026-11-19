# Calculate river loads

Streamlit app for estimating river loads (also knows as fluxes) from user-supplied monitoring data.

The UI is extensively "vibe coded" using Microsoft Copilot, but results (i.e. estimated loads) have been independently validated.

## Running the Streamlit app

### Option 1: From JupyterHub

 1. Open a terminal on the JupyterHub and `cd` into the `load_est_app` directory
    
 2. Run `streamlit run Home.py`

 3. Open a new browser tab and navigate to https://hub.p.niva.no/hub/user-redirect/proxy/8501/

### Option 2: Docker

 1. Clone the repository and build the Dockerfile with `docker build -t load_est_app .`
    
 2. Start the container with `docker run -p 8501:8501 load_est_app`

 3. Open a new tab and navigate to http://localhost:8501

 ## Deployed Streamlit App

The app is deployed publicly at https://load-est-app.p.niva.no/.