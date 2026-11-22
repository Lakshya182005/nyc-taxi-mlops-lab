# 004: Ingest via COPY into Redshift Tables

Stage: S1 · Date: 2026-11-22 · Author: Lakshya Agrawal · Drafted by agent: yes

## Choice

Ingest landed monthly Parquet trip files into local Redshift storage (`ingest.raw_trips`) using the Redshift `COPY` command rather than querying external tables in-place via Redshift Spectrum.

## Rejected alternative

Querying landed files directly in Amazon S3 using Redshift Spectrum external schemas and tables.

## Why

1. **Performance of Downstream Marts & Transformations:** Materializing `staging.stg_trips` and `marts.zone_hour_stats` performs multiple aggregations, joins against `taxi_zones`, and window operations. Having data locally on Redshift columnar storage (`ra3.large` managed storage) provides significantly lower latency and eliminates external scan bottlenecks.
2. **Predictable Query Costs:** Redshift Spectrum incurs an additional per-query scan charge ($5.00 per TB scanned). With Dagster sensor runs, feature engineering jobs, and ad-hoc exploratory queries querying the same historical months repeatedly, local storage avoids cumulative external query fees within the Learner Lab credit cap.
3. **Idempotency & Clean Partition Replacement:** Ingestion with `COPY` into a dedicated table partitioned/keyed by month allows clean transactional truncation or delete/insert per month, avoiding dirty reads from partially uploaded S3 files.

## What would show this was wrong

If monthly raw data volumes exceeded local Redshift cluster storage capacity (e.g. multi-terabyte datasets beyond the 100 GB lab limit) or if raw trip data was accessed so infrequently that storage costs outweighed scan costs.
