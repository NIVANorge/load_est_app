# Model Fit Metrics

This document describes the model fit and trend diagnostics reported by the load estimation app. These metrics aim to help users assess both the reliability of the underlying WRTDS model and the interpretation of estimated load changes.

---

## year_start

The first year included in the EGRET pair analysis used to estimate long-term load change.

---

## year_end

The last year included in the EGRET pair analysis used to estimate long-term load change.

---

## n_samples

Number of chemistry samples used to fit the WRTDS model.

---

## n_censored

Number of chemistry samples reported as censored values (for example "<0.002 mg/L").

---

## pct_censored

Percentage of chemistry samples that were censored.

---

## r2_log

Coefficient of determination (R²) comparing observed and predicted concentrations on a logarithmic scale.

This metric measures how well the model reproduces observed concentration variability. Higher values indicate better agreement between observations and model predictions.

**Note:** For nutrient and water-quality datasets, values are often lower than users may expect from traditional regression models. Low R² values do not necessarily imply unreliable load estimates.

---

## rmse_log

Root Mean Square Error (RMSE) of model predictions on the logarithmic concentration scale.

Measures the typical size of prediction errors. Lower values indicate better predictive performance.

---

## mean_residual_log

Average prediction error on the logarithmic concentration scale. 

| Value | Meaning |
|---------|---------|
| Positive | Model tends to overpredict concentration |
| Negative | Model tends to underpredict concentration |
| Near zero | Little systematic bias |

---

## flux_bias

Estimated bias in predicted flux at sampled dates. Calculated by comparing predicted and observed fluxes.

Note that a model can have relatively low concentration R² but still provide reliable load estimates if flux bias is small.

| Value | Meaning |
|---------|---------|
| Positive | Model tends to overpredict flux |
| Negative | Model tends to underpredict flux |
| Near zero | Little systematic bias |

---

## flux_bias_low

Flux bias calculated assuming censored observations are equal to their lower bound. Provides a conservative estimate of uncertainty associated with censored observations.

For datasets with little or no censoring, this value will be similar to `flux_bias`.

---

## flux_bias_high

Flux bias calculated assuming censored observations are equal to their upper bound. Provides an alternative estimate of uncertainty associated with censored observations.

Large differences between `flux_bias_low` and `flux_bias_high` indicate that censoring may substantially affect results.

---

## corr_residual_flow

Correlation between model residuals and streamflow. Checks whether the model systematically over- or underpredicts concentrations at certain flow conditions.

| Value | Meaning |
|---------|---------|
| Near zero | No obvious flow-related bias |
| Strong positive | Bias increases with flow |
| Strong negative | Bias decreases with flow |

---

## corr_residual_time

Correlation between model residuals and time. Checks whether prediction errors change systematically over the monitoring period.

| Value | Meaning |
|---------|---------|
| Near zero | No obvious time-related bias |
| Positive | Increasing bias over time |
| Negative | Decreasing bias over time |

---

## flux_change_pct

Estimated percentage change in annual load between `year_start` and `year_end`. This estimate is produced using EGRET's pair analysis.

| Value | Meaning |
|---------|---------|
| Positive | Load increased |
| Negative | Load decreased |

---

## flux_cqtc_pct

Contribution of water-quality changes independent of streamflow to the overall load change. 

CQTC stands for **Concentration-Discharge Trend Component**. It estimates how much of the overall load change is attributable to changes in water quality after accounting for streamflow effects.

---

## flux_qtc_pct

Contribution of streamflow change to the overall load change.

QTC stands for **Flow Trend Component**. It estimates how much of the overall load change is attributable to changes in runoff and streamflow.

---

## quality

Overall assessment of model-quality. This is a heuristic/subjective indicator derived from:

 * Number of samples
 * Percentage censored
 * Flux bias
 * Residual-flow correlation
 * Residual-time correlation

Results are indicative ("rules of thumb"), rather than statistically rigorous.

#### `Good`

Typically indicates:

- Adequate sample count
- Limited censoring
- Small flux bias
- No obvious flow-related bias
- No obvious time-related bias

#### `Moderate`

The model could be useful, but one or more diagnostic indicators suggest increased uncertainty.

#### `Poor`

Results should be interpreted cautiously. Model diagnostics indicate substantial uncertainty or limited supporting data.