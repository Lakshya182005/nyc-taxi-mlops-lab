# 010: Load at start-up or reload on alias change

Stage: S3 · Date: 2026-11-22 · Author: Lakshya Agrawal · Drafted by agent: yes

## Choice

Hot reload via an in-process HTTP endpoint (`POST /reload`). The serving container loads the new model into memory while continuing to serve incoming `/predict` requests with the current model version, performing an atomic pointer swap only once the new model is fully initialized.

## Rejected alternative

Restarting or recreating the container on alias change (load only at start-up).

## Why

Loading a model at container start-up drops connections or creates a service outage for the duration of the restart (15–30 seconds), during which the app falls back to the static median. In contrast, in-process reloading maintains continuous serving availability with zero downtime.

## What would show this was wrong

Memory exhaustion (OOM) or memory leaks in the serving process caused by co-hosting two models during the reload transition, or Python interpreter state corruption across repeated model swaps requiring a clean process restart.
