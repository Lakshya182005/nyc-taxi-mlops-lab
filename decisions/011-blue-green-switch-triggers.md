# 011: What triggers the blue-green switch

Stage: S3 · Date: 2026-11-22 · Author: Lakshya Agrawal · Drafted by agent: yes

## Choice

Automated two-step smoke testing before flipping traffic: the deployment job verifies `/version` (confirming git SHA or image tag) and issues a synthetic `/predict` request with valid payload directly to the idle colour via Traefik's `X-Lab-Color` routing header. Traefik traffic is switched to the new colour automatically if and only if both checks succeed.

## Rejected alternative

Manual verification before flipping traffic, or relying solely on container health checks (`/healthz`).

## Why

Relying solely on `/healthz` risks flipping traffic to an application that cannot reach internal services or parse model payloads. Running synthetic `/predict` directly through Traefik proves end-to-end routing, payload deserialization, and fallback/model connectivity before any live rider traffic reaches the container. Automated flipping avoids human latency while the idle colour is retained for immediate rollback.

## What would show this was wrong

Subtle runtime failures, edge-case payload errors, or performance degradations that slip past single-payload synthetic smoke tests, requiring live traffic canary splits or automated rollbacks based on production error rates.
