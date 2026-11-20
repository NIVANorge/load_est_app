packages <- c(
    "EGRET",
    "dplyr",
    "readr",
    "lubridate"
)

repo <- "https://cloud.r-project.org"

for (package in packages) {

    cat("Installing", package, "\n")

    install.packages(
        package,
        repos = repo,
        Ncpus = parallel::detectCores()
    )

    cat("Testing", package, "\n")

    if (!requireNamespace(package, quietly = TRUE)) {
        stop(paste("Failed to install:", package))
    }
}

cat("All packages installed successfully\n")