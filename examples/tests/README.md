# Error datasets

This folder contains test datasets designed to trigger errors in the app for testing.

 * `too_short.xlsx`.  A single series with too few observations.
 * `one_too_short.xlsx`. A dataset containing two series, one of which is too short. The longer series should be processed successfully, while the short one is skipped.
 * `too_censored.xlsx`. A single series where too many of the values are censored (i.e. below the limit of quantification).