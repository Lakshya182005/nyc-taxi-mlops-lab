# 003: Immutable Git SHA Tagging Scheme for Container Images

Stage: S0 · Date: 2026-11-22 · Author: Lakshya Agrawal · Drafted by agent: yes

## Choice

Tag container images pushed to GHCR with the short Git commit SHA (`sha-${GITHUB_SHA::7}`).

## Rejected alternative

Using mutable tags such as `latest` or relying exclusively on sequential CI run numbers (`v0.1.${GITHUB_RUN_NUMBER}`).

## Why

A short git SHA guarantees an exact 1:1, immutable mapping between the repository state at commit time and the running container artifact. This makes diagnosing deployment issues and rolling back to a known-good commit instantaneous and unambiguous. Mutable tags like `latest` conceal drift, break reproducibility, and prevent deterministic rollback.

## What would show this was wrong

If downstream consumers or external non-technical stakeholders required human-ordered semantic versioning strings (e.g., `v1.2.0`) in deployment manifests without access to git commit history.
