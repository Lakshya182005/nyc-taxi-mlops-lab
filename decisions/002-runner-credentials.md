# 002: Use Host IAM Instance Profile for Runner and CD Operations

Stage: S0 · Date: 2026-11-22 · Author: Lakshya Agrawal · Drafted by agent: yes

## Choice

Use the EC2 host's pre-configured IAM instance profile (`LabRole` / `LabInstanceProfile`) for runner and deployment operations on AWS instead of static session credentials stored in GitHub Secrets.

## Rejected alternative

Storing temporary Learner Lab session credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) as GitHub repository secrets and using them in CI/CD runners.

## Why

Learner Lab session credentials expire every few hours, requiring tedious manual re-exporting and introducing failure points into automated runs. Furthermore, committing credentials into GitHub secrets risks leakage through logs, build artifacts, or fork workflows. The EC2 instance profile is managed by AWS, automatically refreshes its tokens via the Instance Metadata Service (IMDSv2), and requires zero credential maintenance across session restarts.

## What would show this was wrong

If a deployment job required permissions strictly absent from `LabRole` that could only be delegated via a separate assumed role with static keys, or if deployments needed to run purely on GitHub-hosted runners outside the AWS VPC.
