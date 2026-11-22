# 009: Training Window and Holdout Evaluation Split

Stage: S2 · Date: 2026-11-22 · Author: Lakshya Agrawal · Drafted by agent: yes

## Choice

Train on a sliding window of the **three months prior to the holdout** (`2024-01` through `2024-03`, capped at 3,000,000 subsampled rows for compute efficiency), and evaluate on the **most recently landed month** (`2024-04`, 500,000 holdout sample). The zone-pair distance lookup (`est_distance_miles`) is aggregated strictly over the training window so that no holdout trips leak into distance estimates.

## Rejected alternative

- Random train/validation/test split across all months: rejected because it introduces temporal data leakage by allowing past trips to be predicted using future trip patterns.
- Single-month training window: rejected because a single month does not capture enough seasonal and weekly zone-pair variance to train robust tree ensembles.
- Training on the full 9.5M rows without subsampling: tests show that fitting on all 9.5M rows yields a negligible 0.02 minute MAE improvement while increasing training time by 2.5x, straining memory and compute limits in Learner Lab.

## Why

A time-based split faithfully replicates production deployment: models trained on past data are evaluated on future, unseen traffic conditions. A 3-month window provides ample coverage of zone pairs and weather/calendar variations while keeping training times under a few minutes. Restricting distance aggregations strictly to the training window prevents target leakage.

## What would show this was wrong

If severe concept drift causes older months in the 3-month window to degrade holdout accuracy compared to training solely on the most recent month, or if seasonal shifts (e.g., summer vs winter travel patterns) require a longer multi-season training window.
