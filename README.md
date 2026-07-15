# S3 ClamAV Scanner

An automated malware-scanning pipeline for files uploaded to Amazon S3 — built around ClamAV, with scan results written directly onto the S3 object as tags so downstream systems can gate on them without a separate database.

## Overview

Every file that lands in an S3 bucket is a potential liability until something has actually looked at it. This project downloads a target object, runs it through ClamAV, and writes the outcome straight back onto the object as S3 tags (`Scanned`, `Result`) — a lightweight pattern that lets any downstream consumer (a Lambda, a pipeline step, a human in the console) check whether a file is safe with a single `HeadObject`/`GetObjectTagging` call instead of querying a separate scan-results store.

The end goal is a fully event-driven, containerized, scale-to-zero pipeline (see [Roadmap](#roadmap)). The current implementation is a working prototype that proves out the core mechanism: **download → scan → tag**.

## What It Does Today

- Downloads a target object from an S3 bucket
- Runs it through ClamAV's `clamscan`
- Interprets the scan's exit code (`0` = clean, `1` = infected, anything else = error)
- Writes the outcome back onto the S3 object as tags: `Scanned=True`, `Result=CLEAN | INFECTED | ERROR`
- Validated against two fixtures: a plain clean text file and an [EICAR test file](https://en.wikipedia.org/wiki/EICAR_test_file) — the industry-standard "fake virus" string used to safely test antivirus tooling without a real payload

## A Real Bug, Not a Toy Demo

Early runs tagged *every* file — clean and infected alike — as `ERROR`. The cause turned out to be in ClamAV itself, not the script: ClamAV 1.5+ verifies its virus database's digital signature against a certs directory (`/etc/clamav/certs`) that doesn't exist on a default install. Without it, `clamscan` can't load its database at all, scans zero files, and exits with code 2 — which the script correctly, if unhelpfully, reported as `ERROR` for every file.

**Fix:** point `clamscan` at a project-local `certs/` directory via `--cvdcertsdir`, created automatically on first run, so the scanner doesn't depend on a system path or root access. Also added logging of `clamscan`'s stdout/stderr whenever a scan errors, so future failures are diagnosable instead of silently collapsing to `ERROR`.

## Tech Stack

- **Python 3 / boto3** — S3 interaction (download, tagging)
- **ClamAV** (`clamscan`, `freshclam`) — malware detection engine and signature updates
- **S3 object tagging** — result delivery mechanism, no extra infrastructure required

## Architecture

**Current (prototype):**

```
S3 bucket ──(script run)──> main.py ──> download file ──> clamscan ──> tag object
                                                                        (Scanned, Result)
```

**Target (production design — see Roadmap):**

```
S3 upload event ──> Lambda / Fargate task (containerized ClamAV) ──> scan
                                                    │
                                                    ├──> tag object (Scanned, Result)
                                                    ├──> notify (SNS/Slack) if infected
                                                    └──> scale to zero when idle
```

## Getting Started

```bash
# Dependencies
pip install boto3
sudo apt install clamav clamav-freshclam

# Pull the latest virus definitions
sudo freshclam

# Configure AWS credentials (any standard method: env vars, ~/.aws/credentials, etc.)

# Set bucket/key in clamav/main.py, then:
python3 clamav/main.py
```

Check the result:

```bash
aws s3api get-object-tagging --bucket <bucket> --key <key>
```

## Roadmap

- [ ] Trigger via native S3 → EventBridge/Lambda event instead of a manual script run
- [ ] Containerize the scanner (Docker), bundling ClamAV and signature definitions into the image
- [ ] Deploy as a scale-to-zero compute target (Lambda or Fargate on-demand)
- [ ] Infrastructure as code (Terraform) for the bucket, event rule, compute, and IAM permissions
- [ ] Notification integration (SNS/Slack) on infected-file detection
- [ ] Scheduled, automated `freshclam` signature updates
