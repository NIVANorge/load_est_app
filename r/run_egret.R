#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(EGRET)
  library(dplyr)
})

# ============================================================
# Quality thresholds
# ============================================================
# Heuristics for summarising WRTDS model quality. These are not 
# EGRET standards. They are intended to flag models that may be 
# poor/inappropriate

GOOD_MIN_SAMPLES <- 100
MODERATE_MIN_SAMPLES <- 50

GOOD_MAX_PCT_CENSORED <- 20
MODERATE_MAX_PCT_CENSORED <- 50

GOOD_MAX_FLUX_BIAS <- 0.15
MODERATE_MAX_FLUX_BIAS <- 0.25

MAX_RESIDUAL_FLOW_CORR <- 0.10
MAX_RESIDUAL_TIME_CORR <- 0.10

# ============================================================
# Arguments
# ============================================================

args <- commandArgs(trailingOnly = TRUE)

if (length(args) != 1) {
  stop(
    paste(
      "Usage:",
      "Rscript run_egret.R",
      "job_directory"
    )
  )
}

job_dir <- normalizePath(
  args[1],
  mustWork = TRUE
)

cat("Starting EGRET\n")
cat(sprintf("Job directory: %s\n", job_dir))

# ============================================================
# Utility function
# ============================================================

run_model <- function(
    sample_file,
    daily_file,
    station_code,
    parameter
) {

  cat(
    sprintf(
      "\nProcessing station=%s parameter=%s\n",
      station_code,
      parameter
    )
  )

  cat("Reading sample data...\n")

  Sample <- readUserSample(
    filePath = dirname(sample_file),
    fileName = basename(sample_file),
    separator = ",",
    format = "%Y-%m-%d"  
  )
  
  n_samples <- nrow(Sample)  
  n_censored <- sum(Sample$Uncen == 0, na.rm = TRUE)  
  pct_censored <- round(100 * n_censored / n_samples, 1)

  cat("Reading daily flow data...\n")

  Daily <- readUserDaily(
    filePath = dirname(daily_file),
    fileName = basename(daily_file),
    separator = ",",
    qUnit = 2, # m3/s
    format = "%Y-%m-%d"
  )

  cat(sprintf("Samples: %d\n", n_samples)) 
  cat(sprintf("Censored values: %d (%.1f %%)\n", n_censored, pct_censored))
  cat(sprintf("Daily flow observations: %d\n", nrow(Daily)))

  INFO <- data.frame(
    shortName      = station_code,
    stationNm      = station_code,
    paramShortName = parameter,
    constitAbbrev  = parameter,
    param.units    = "mg/L",
    drainSqKm      = NA,
    paStart        = 1,
    paLong         = 12
  )

  cat("Building eList...\n")

  eList <- as.egret(
    INFO = INFO,
    Daily = Daily,
    Sample = Sample
  )

  cat("Running WRTDS...\n")

  # Bug in EGRET skips data overview if the frame contains censored data
  # Ensure the summary is printed regardless  
  if (!all(!is.na(Sample))) {
  
    EGRET:::dataOverview(
      Daily,
      Sample
    )
  
  }
    
  eList <- modelEstimation(
    eList,
  )
 
  # ----------------------------------------------------------
  # Goodness-of-fit statistics
  # ----------------------------------------------------------
  s <- eList$Sample
 
  valid <- (
    s$ConcAve > 0 &
    s$ConcHat > 0
  )
  
  resid_log <- log(s$ConcHat) - log(s$ConcAve)
 
  r2_log <- cor(
    log(s$ConcAve[valid]),
    log(s$ConcHat[valid]),
    use = "complete.obs"
  )^2
 
  rmse_log <- sqrt(
    mean(
      resid_log^2,
      na.rm = TRUE
    )
  )
 
  mean_residual_log <- mean(
    resid_log,
    na.rm = TRUE
  )
 
  fb <- EGRET:::fluxBiasStat(s)
 
  flux_bias_low <- fb$bias1[1]
  flux_bias_high <- fb$bias2[1]
  flux_bias <- fb$bias3[1]
 
  corr_residual_flow <- cor(
    resid_log,
    s$LogQ,
    use = "complete.obs"
  )
 
  corr_residual_time <- cor(
    resid_log,
    s$DecYear,
    use = "complete.obs"
  )

  # Round diagnostics for output
  r2_log <- round(r2_log, 3)
  rmse_log <- round(rmse_log, 3)
  mean_residual_log <- round(mean_residual_log, 3)
  flux_bias <- round(flux_bias, 3)
  flux_bias_low <- round(flux_bias_low, 3)
  flux_bias_high <- round(flux_bias_high, 3)
  corr_residual_flow <- round(corr_residual_flow, 3)
  corr_residual_time <- round(corr_residual_time, 3)

  if (!is.finite(flux_bias)) {
    flux_bias <- NA_real_
  }
   
  quality <-
    if (
      n_samples >= GOOD_MIN_SAMPLES &&
      pct_censored <= GOOD_MAX_PCT_CENSORED &&
      abs(flux_bias) < GOOD_MAX_FLUX_BIAS &&
      abs(corr_residual_flow) < MAX_RESIDUAL_FLOW_CORR &&
      abs(corr_residual_time) < MAX_RESIDUAL_TIME_CORR
    ) {
      "Good"
    } else if (
      n_samples >= MODERATE_MIN_SAMPLES &&
      pct_censored <= MODERATE_MAX_PCT_CENSORED &&
      abs(flux_bias) < MODERATE_MAX_FLUX_BIAS
    ) {
      "Moderate"
    } else {
      "Poor"
    }
   
  cat("Extracting annual results...\n")

  tr <- tableResults(
    eList
  )

  # ----------------------------------------------------------
  # EGRET pair analysis
  # ----------------------------------------------------------
  
  year1 <- min(tr$Year) - 1
  year2 <- max(tr$Year) - 1
  
  pairOut <- EGRET::runPairs(
    eList,
    year1,
    year2,
    windowSide = 7
  )
    
  flux_change_pct <- (
    attr(pairOut, "Other")$PercentChangeFlux[
      "Total Percent Change"
    ]
  )
  
  flux_cqtc_pct <- (
    attr(pairOut, "Other")$PercentChangeFlux[
      "CQTC Percent"
    ]
  )
  
  flux_qtc_pct <- (
    attr(pairOut, "Other")$PercentChangeFlux[
      "QTC Percent"
    ]
  )
  
  flux_change_pct <- round(flux_change_pct, 1)  
  flux_cqtc_pct <- round(flux_cqtc_pct, 1)  
  flux_qtc_pct <- round(flux_qtc_pct, 1)
      
  # ----------------------------------------------------------
  # Get result time series
  # ----------------------------------------------------------
    
  flux_col <- grep(
    "^Flux",
    names(tr),
    value = TRUE
  )

  fn_flux_col <- grep(
    "^FN Flux",
    names(tr),
    value = TRUE
  )

  if (length(flux_col) != 1) {

    stop(
      paste(
        "Could not uniquely identify flux column:",
        paste(names(tr), collapse = ", ")
      )
    )

  }

  if (length(fn_flux_col) != 1) {

    stop(
      paste(
        "Could not uniquely identify FN flux column:",
        paste(names(tr), collapse = ", ")
      )
    )

  }

  # ----------------------------------------------------------
  # Determine units
  # ----------------------------------------------------------

  get_tonnes_multiplier <- function(col_name) {

    if (
      grepl(
        "10\\^6kg/yr",
        col_name
      )
    ) {
      return(1000)
    }

    if (
      grepl(
        "10\\^3kg/yr",
        col_name
      )
    ) {
      return(1)
    }

    if (
      grepl(
        "\\[kg/yr\\]",
        col_name
      )
    ) {
      return(0.001)
    }

    stop(
      paste(
        "Unknown flux units in column:",
        col_name
      )
    )

  }

  flux_multiplier <- (
    get_tonnes_multiplier(
      flux_col
    )
  )

  fn_flux_multiplier <- (
    get_tonnes_multiplier(
      fn_flux_col
    )
  )

  annual_df <- data.frame(
    station_code = station_code,
    parameter = parameter,
    year = tr[["Year"]] - 1,
    tonnes = (
      tr[[flux_col]]
      * flux_multiplier
    )
  )
  
  fn_df <- data.frame(
    station_code = station_code,
    parameter = parameter,
    year = tr[["Year"]] - 1,
    tonnes = (
      tr[[fn_flux_col]]
      * fn_flux_multiplier
    )
  )


  diagnostics_df <- data.frame(
    station_code = station_code,
    parameter = parameter,

    year_start = year1,
    year_end = year2,

    n_samples = n_samples,
    n_censored = n_censored,
    pct_censored = pct_censored,

    r2_log = r2_log,
    rmse_log = rmse_log,
    mean_residual_log = mean_residual_log,

    flux_bias = flux_bias,
    flux_bias_low = flux_bias_low,
    flux_bias_high = flux_bias_high,

    corr_residual_flow = corr_residual_flow,
    corr_residual_time = corr_residual_time,

    flux_change_pct = flux_change_pct,
    flux_cqtc_pct = flux_cqtc_pct,
    flux_qtc_pct = flux_qtc_pct,

    quality = quality,

    status = "OK",
    message = "",

    stringsAsFactors = FALSE
  )

  list(
    annual = annual_df,
    fn = fn_df,
    diagnostics = diagnostics_df
  )

}

# ============================================================
# Locate models
# ============================================================

model_dirs <- list.dirs(
  job_dir,
  recursive = FALSE,
  full.names = TRUE
)

if (length(model_dirs) == 0) {
  stop(
    paste(
      "No model directories found in",
      job_dir
    )
  )
}

cat(
  sprintf(
    "Found %d model folders\n",
    length(model_dirs)
  )
)

# ============================================================
# Results containers
# ============================================================

annual_results <- list()
fn_results <- list()
diagnostics <- list()

# ============================================================
# Process models
# ============================================================

for (i in seq_along(model_dirs)) {

  model_dir <- model_dirs[i]

  folder_name <- basename(
    model_dir
  )

  parts <- strsplit(
    folder_name,
    "__"
  )[[1]]

  if (length(parts) != 2) {

    diagnostics[[length(diagnostics) + 1]] <- data.frame(
      station_code = NA_character_,
      parameter = NA_character_,

      year_start = NA_real_,
      year_end = NA_real_,

      n_samples = NA_real_,
      n_censored = NA_real_,
      pct_censored = NA_real_,

      r2_log = NA_real_,
      rmse_log = NA_real_,
      mean_residual_log = NA_real_,

      flux_bias = NA_real_,
      flux_bias_low = NA_real_,
      flux_bias_high = NA_real_,

      corr_residual_flow = NA_real_,
      corr_residual_time = NA_real_,

      flux_change_pct = NA_real_,
      flux_cqtc_pct = NA_real_,
      flux_qtc_pct = NA_real_,

      quality = NA_character_,

      status = "ERROR",
      message = paste(
        "Invalid folder name:",
        folder_name
      ),

      stringsAsFactors = FALSE
    )

    next
  }

  station_code <- parts[1]
  parameter <- parts[2]

  sample_file <- file.path(
    model_dir,
    "sample.csv"
  )

  daily_file <- file.path(
    model_dir,
    "daily.csv"
  )

  cat(
    sprintf(
      "\n[%d/%d] %s %s\n",
      i,
      length(model_dirs),
      station_code,
      parameter
    )
  )

  tryCatch(

    {

      result <- run_model(
        sample_file = sample_file,
        daily_file = daily_file,
        station_code = station_code,
        parameter = parameter
      )

      annual_results[[length(annual_results) + 1]] <- result$annual

      fn_results[[length(fn_results) + 1]] <- result$fn

      diagnostics[[length(diagnostics) + 1]] <- (
        result$diagnostics
      )

      cat("SUCCESS\n")

    },

    error = function(e) {

      msg <- conditionMessage(e)

      cat(
        sprintf(
          "FAILED: %s\n",
          msg
        )
      )

      diagnostics[[length(diagnostics) + 1]] <- data.frame(
        station_code = station_code,
        parameter = parameter,

        year_start = NA_real_,
        year_end = NA_real_,

        n_samples = NA_real_,
        n_censored = NA_real_,
        pct_censored = NA_real_,

        r2_log = NA_real_,
        rmse_log = NA_real_,
        mean_residual_log = NA_real_,

        flux_bias = NA_real_,
        flux_bias_low = NA_real_,
        flux_bias_high = NA_real_,

        corr_residual_flow = NA_real_,
        corr_residual_time = NA_real_,

        flux_change_pct = NA_real_,
        flux_cqtc_pct = NA_real_,
        flux_qtc_pct = NA_real_,

        quality = NA_character_,

        status = "ERROR",
        message = msg,

        stringsAsFactors = FALSE
      )

    }

  )

}

# ============================================================
# Merge outputs
# ============================================================

if (length(annual_results) > 0) {

  annual_df <- bind_rows(
    annual_results
  )

} else {

  annual_df <- data.frame(
    station_code = character(),
    parameter = character(),
    year = integer(),
    tonnes = numeric()
  )

}

if (length(fn_results) > 0) {

  fn_df <- bind_rows(
    fn_results
  )

} else {

  fn_df <- data.frame(
    station_code = character(),
    parameter = character(),
    year = integer(),
    tonnes = numeric()
  )

}

if (length(diagnostics) > 0) {

  diag_df <- bind_rows(
    diagnostics
  )

} else {

  diag_df <- data.frame(
    station_code = character(),
    parameter = character(),

    year_start = numeric(),
    year_end = numeric(),

    n_samples = numeric(),
    n_censored = numeric(),
    pct_censored = numeric(),

    r2_log = numeric(),
    rmse_log = numeric(),
    mean_residual_log = numeric(),

    flux_bias = numeric(),
    flux_bias_low = numeric(),
    flux_bias_high = numeric(),

    corr_residual_flow = numeric(),
    corr_residual_time = numeric(),

    flux_change_pct = numeric(),
    flux_cqtc_pct = numeric(),
    flux_qtc_pct = numeric(),

    quality = character(),

    status = character(),
    message = character(),

    stringsAsFactors = FALSE
  )

}

# ============================================================
# Write outputs
# ============================================================

annual_file <- file.path(
  job_dir,
  "annual_loads.csv"
)

fn_file <- file.path(
  job_dir,
  "flow_normalised_loads.csv"
)

diag_file <- file.path(
  job_dir,
  "diagnostics.csv"
)

write.csv(
  annual_df,
  annual_file,
  row.names = FALSE
)

write.csv(
  fn_df,
  fn_file,
  row.names = FALSE
)

write.csv(
  diag_df,
  diag_file,
  row.names = FALSE
)

cat("\n")
cat("=====================================\n")
cat("Processing complete\n")
cat("=====================================\n")

cat(
  sprintf(
    "Annual results: %s\n",
    annual_file
  )
)

cat(
  sprintf(
    "Flow-normalised results: %s\n",
    fn_file
  )
)

cat(
  sprintf(
    "Diagnostics: %s\n",
    diag_file
  )
)

cat("Finished\n")