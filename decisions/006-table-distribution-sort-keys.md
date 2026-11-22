# 006: Redshift Distribution and Sort Keys for Trip Tables

Stage: S1 · Date: 2026-11-22 · Author: Lakshya Agrawal · Drafted by agent: yes

## Choice

Define explicit distribution and sort keys tailored to workload access patterns:
- `ingest.raw_trips`: `diststyle auto`, `sortkey(tpep_pickup_datetime)`
- `staging.stg_trips`: `distkey(pickup_zone_id)`, `sortkey(pickup_at)`

## Rejected alternative

Using default / unkeyed tables (`diststyle auto` without sort keys, or uniformly using `diststyle all`).

## Why

1. **Sort Key on Pickup Timestamp:** The primary slice filter across all analytical transformations, Dagster partition jobs, and feature pipelines is the monthly time window (`pickup_at`). Collocating rows in 1MB zone blocks sorted by pickup timestamp enables Redshift zone maps to skip non-matching blocks entirely during partition-scoped materializations.
2. **Distribution Key on `pickup_zone_id` for Staging:** `zone_hour_stats` joins `stg_trips` with `taxi_zones` on zone ID. With `taxi_zones` small enough to be distributed to all nodes (`diststyle all`), co-locating `stg_trips` by `pickup_zone_id` guarantees local in-memory hash joins with zero network redistribution across slices.

## What would show this was wrong

Severe data skew across Redshift slices caused by disproportionately busy pickup zones (e.g. JFK or Midtown causing slice skew > 20%), or queries predominantly filtering on dropoff attributes rather than pickup time and location.
