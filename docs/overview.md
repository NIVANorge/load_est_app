# Load Estimation App

## Overview

The Load Estimation App estimates long-term nutrient and pollutant loads in rivers using the [EGRET (Exploration and Graphics for RivEr Trends) package](https://doi-usgs.github.io/EGRET/) for R. It is designed to support water quality assessments by combining concentration measurements with daily streamflow records to estimate loads, evaluate trends, and separate the effects of changing water quality from changes in hydrology.

# Workflow summary

The load estimation process consists of five main stages:

1. Data import and validation
2. Data preprocessing and user review
3. EGRET model fitting (WRTDS)
4. Load and trend estimation
5. Reporting and visualisation

The figure below summarises the workflow:

```text
User uploads template ◄─────────┐
          │                     │
          ▼                     │
   Data validation              │
          │                     │
          ▼                     │
  Average duplicates &          │
  fill short flow gaps          │
          │                     │
          ▼                     │
   User reviews data ───────────┘
          │
          ▼
      EGRET WRTDS
          │
          ▼
    Load estimation
          │
          ▼
   Flow normalisation
          │
          ▼
Trend and change analysis
          │
          ▼
 Results and diagnostics
```

# Input data requirements

The application requires two datasets:

## 1. Water chemistry data

Discrete water chemistry measurements containing:

- Sampling date
- Concentration value(s)
- Optional censoring information (e.g. values above or below quantification limits, expressed as `>` or `<`)

## 2. Flow data

A continuous daily streamflow time series containing:

- Date
- Daily mean discharge

The flow record should span the entire analysis period and ideally extend beyond the water quality monitoring record. The discharge dataset should not contain any gaps.

# Data preprocessing

Before any load calculations are performed, the application conducts several preprocessing steps to improve data quality and ensure compatibility with EGRET.

## Averaging duplicate chemistry samples

When multiple observations occur at the same site on the same date, concentration values are averaged. This prevents individual sampling events from being over-represented during model fitting.

## Filling short flow gaps

EGRET requires a continuous daily flow record, but flow series often contain gaps. The application automatically identifies missing daily flows and fills gaps using linear interpolation. Note that large gaps (more than a few days) in the flow series **may produce unreliable load estimates**.

# EGRET

EGRET (Exploration and Graphics for RivEr Trends) is an R package developed by the United States Geological Survey (USGS) for analysing river water quality trends and estimating constituent loads.

Rather than fitting a simple concentration-versus-time relationship, EGRET accounts for both:

- Temporal changes in water chemistry
- Variations in river discharge

This is important because constituent concentrations often depend strongly on streamflow.

# WRTDS

The primary modelling approach used by EGRET is **Weighted Regressions on Time, Discharge, and Season (WRTDS)**, which estimate concentration as a smooth function of time, discharge and season. WRTDS model are flexible and can represent:

- Non-linear trends
- Gradual changes through time
- Changing concentration-flow relationships
- Seasonal behaviours

# Load estimation

For every day in the analysis period, EGRET combines observed streamflow and modelled concentration to estimate daily loads. These are then aggregated to give annual totals.

## Flow-normalised loads

Annual loads have high variability because some years are wetter than others. Flow-normalisation removes the influence of year-to-year hydrological variability to estimate what the annual load would have been if every year experienced the same long-term distribution of streamflows.

Changes in flow-normalised loads therefore primarily reflect changes in factors such as land use, wastewater inputs, agricultural practices and catchment management, rather than changes in weather or runoff.

# Change analysis

One of EGRET's most useful features is its ability to partition load changes into components attributable to (i) changes in streamflow/runoff, and (ii) changes in water chemistry that are independent of streamflow.

- The **Discharge Trend Component (QTC)** represents the portion of the load change caused by changes in river flow (e.g. weather variability, climate change or long-term changes in runoff).
- The **Concentration-Discharge Trend Component (CQTC)** represents the portion of the load change arising from changes in water quality independent of streamflow (e.g. reduced nutrient inputs, wastewater treatment improvements, or changing land management practices).

Together these components explain the total change in load between two time points.

# Trend analysis

In addition to the EGRET-based change analysis, the application evaluates long-term trends using two widely used non-parametric statistical methods:

- Mann-Kendall trend test
- Sen's slope estimator

These methods are robust to non-normal data distributions and are commonly used in environmental monitoring programmes.

## Mann-Kendall test

The Mann-Kendall test assesses whether values increase or decrease monotonically over time. The test does not assume that model residuals are normally distributed and is relatively insensitive to outliers, making it well suited for water quality and load datasets.

The application reports:

- Trend direction (increasing or decreasing)
- p-value
- Statistical significance

A significant positive result indicates an increasing trend through time, while a significant negative result indicates a decreasing trend.

## Sen's slope

Sen's slope estimates the magnitude of the trend detected by the Mann-Kendall test i.e. it provides an estimate of how quickly conditions are changing over time. The method calculates the median rate of change between all possible pairs of observations and is robust to extreme values.

# Model Diagnostics

The application calculates several diagnostics to help assess model performance. These are explained in more detail [here](https://github.com/NIVANorge/load_est_app/blob/main/docs/model_fit_metrics.md).