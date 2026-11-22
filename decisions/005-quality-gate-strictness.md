# 005: Quality Gate Strictness (Blocking vs Warning)

Stage: S1 · Date: 2026-11-22 · Author: Lakshya Agrawal · Drafted by agent: yes

## Choice

Enforce a tiered quality gate policy: structural schema integrity and data completeness checks are strictly **blocking** (halting the pipeline before ingestion or before mart updates), while data distribution anomalies (e.g., volume fluctuations, trip duration outliers) are configured as **warnings**.

## Rejected alternative

Making all quality checks strictly blocking, or conversely making all checks advisory (warning-only).

## Why

1. **Schema & Contract Drift (Blocking):** As mandated by `contracts/platform.yaml`, `schema_contract` on `trip_files` must block before `raw_trips` runs. If Parquet columns, column order, or data types diverge (such as upstream schema variations in 2023 or 2025), proceeding with positional `COPY` would silently corrupt warehouse columns.
2. **Reconciliation & Completeness (Blocking):** A row count mismatch between the landed Parquet metadata and Redshift loaded rows indicates a partial or truncated load. Blocking ensures corrupted partitions never reach downstream marts.
3. **Real-world Noise & Anomalies (Warning):** TLC taxi datasets frequently contain minor outliers (e.g. negative fare amounts, trips with extreme durations or zero passenger counts). Making these blocking would cause pipeline failures on valid monthly batches that downstream feature engineering models can easily filter out.

## What would show this was wrong

If real downstream production issues (such as broken dashboards or model prediction failures) trace back to unblocked anomalies that were logged only as warnings, or if critical upstream pipeline runs fail repeatedly on benign data artifacts.
