# 007: What Stays in the Notebook and What Moves into the Pipeline

Stage: S2 · Date: 2026-11-22 · Author: Lakshya Agrawal · Drafted by agent: yes

## Choice

**Pipeline (Dagster, executed automatically without human intervention):** feature extraction (`staging.trip_features`), dataset UNLOAD (`training_set`), model training (`trained_model`), evaluation report (`eval_report`), blocking automated promotion gate (`beats_champion`), and setting the `challenger` alias in MLflow.

**Notebook (Exploration only):** data exploration, visualizations, hyperparameter tuning experiments, and feature importance analyses on subsamples. The notebook logs to its own experiment (`trip-duration-notebook`), never registers models to the production registry, and never assigns model aliases.

## Rejected alternative

Running training and model registration directly inside the Jupyter notebook, treating the pipeline merely as an automated data provider. While faster for ad-hoc experimentation, models trained this way depend on volatile in-memory cell state, lack reproducible provenance, and allow unvetted models to be registered and aliased manually without passing strict gating checks.

## Why

Any component that influences what serves live user inference requests must be fully repeatable, auditable, and automated. Placing model training and evaluation inside the Dagster pipeline guarantees that every model version carries verified git commit tags, dataset window metadata, and passing automated gates. Conversely, data science exploration demands rapid iteration, ad-hoc plotting, and throwaway prototypes. Separating concerns at the boundary of "can this affect serving?" gives data scientists exploratory freedom while maintaining production rigor.

## What would show this was wrong

If experimental findings in the notebook cannot be reproduced within the pipeline due to environment or data divergence, or if pipeline retraining overhead slows down rapid model iterations excessively during active research.
