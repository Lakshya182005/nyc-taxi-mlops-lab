# 001: Restrict App Ingress to Specific Client CIDRs

Stage: S0 · Date: 2026-11-22 · Author: Lakshya Agrawal · Drafted by agent: yes

## Choice

Restrict inbound HTTP traffic (port 80) to the app host's security group to explicit CIDR blocks: the student's workstation IP (`115.244.141.202/32`) and the grader/instructor IP.

## Rejected alternative

Opening ingress to all IPv4 addresses (`0.0.0.0/0`).

## Why

In AWS Academy Learner Lab, resources operate under shared infrastructure with credit constraints and strict security guidelines. Exposing port 80 to the entire internet invites automated vulnerability scanners and bot probes, generating unnecessary request volume and exposure. Restricting to client `/32` CIDRs enforces least privilege while meeting all testing and grading requirements.

## What would show this was wrong

Frequent workstation IP changes (e.g. mobile networks or dynamic ISP leases) breaking access repeatedly, or if the grader needs to access the service from dynamic/unpredictable IP ranges that cannot be statically whitelisted.
