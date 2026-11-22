# 008: Promotion Metric and Margin

Stage: S2 · Date: 2026-11-22 · Author: Lakshya Agrawal · Drafted by agent: yes

## Choice

A newly trained model version becomes `challenger` only if its holdout Mean Absolute Error (`mae_min`) improves upon the benchmark (the current champion, or the v1 baseline prior to a champion) by at least **0.5% (MARGIN = 0.005)**, and its single-row p95 prediction latency is within **50.0 ms**. Slice MAEs (airport, Manhattan, outer, night) are computed, logged, and tagged for observability, but only overall holdout MAE and latency act as blocking gates.

## Rejected alternative

- Requiring strictly lower MAE without an improvement margin ("any improvement"), which would promote models on statistical noise.
- Setting a very large margin (e.g. 5% or 10%), which would reject incremental improvements on mature production models.
- Requiring non-regression across every single slice, which risks blocking good global models due to high variance on low-volume slices.

## Why

Mean Absolute Error (MAE) directly reflects expected error in minutes on real passenger rides and is less susceptible to distortion by extreme outlier durations (e.g. multi-hour gridlock or data errors) than Root Mean Squared Error (RMSE). A 0.5% margin prevents promoting models whose apparent advantage is merely random variation on the holdout partition. The 50 ms p95 in-process latency budget ensures the model easily complies with the end-to-end serving SLO once network and serialization overhead are included.

## What would show this was wrong

If a model promoted on overall MAE degrades customer experience noticeably on critical high-value slices (such as airport trips), or if real-world serving latency exceeds SLO thresholds due to unexpected feature lookup delays.
