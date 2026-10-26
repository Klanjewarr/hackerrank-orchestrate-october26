# HackerRank Orchestrate — October 2026: Ghost Data Still Exists

An AI-powered digital forensics and deletion-audit agent that independently verifies data deletion compliance across commerce platforms, distributed databases, replicas, observability logs, search indexes, analytics warehouses, and backup archives.

---

## 1. Architecture & Solution Overview

The system architecture implements a zero-trust forensic audit engine:
- **Identity Resolution (`src/identity_resolution.py`):** Reconstructs unified subject graphs across current snapshots (`user_identities.csv`), historical audit changes (`user_audit_log.csv`), email changes, phone changes, SHA-256 hashes, and cross-system activity links (`LINK_RESOURCE_IDENTITY`).
- **Evidence Ingestion (`src/evidence_ingestion.py`):** Deterministically parses SQLite snapshots, structured JSON service exports and snapshot bundles, syslog/logfmt distributed trace logs (`tr-*` and `rb-*`), plain-text shift handovers, and PDF attachments.
- **Temporal State Engine (`src/temporal_state.py`):** Evaluates resource state strictly at or before `audit_at`. Detects replication drift between primary and failover replicas, unredacted PII on account tombstones and support tickets, un-anonymized telemetry, active integration data flows, and unblocked backup archives.
- **Remediation & Step Ordering (`src/remediation_planner.py` & `src/step_ordering.py`):** Enforces strict phase ordering (`FINDING` -> `REMEDIATION` -> `VERIFICATION`), remediation precedence (stopping flows and blocking restores before modifying dependent data), and 1-based sequential step numbering.
- **Validation Checklist (`src/validate_output.py`):** Enforces the complete 20-point checklist on `output.csv`.

---

## 2. Requirements & Setup

### Requirements
- Python 3.10+ (tested on Python 3.14)
- Dependencies: `pypdf>=5.0.0`, `pillow>=10.0.0`

### Installation
```bash
pip install -r requirements.txt
```

---

## 3. Running the Solution

### Generate Full Predictions (`output.csv` — 518 Requests)
Run the pipeline to process all 518 evaluation requests and generate the final `output.csv` at the repository root:
```bash
python code/main.py
```

### Evaluate on Sample Dataset (32 Requests)
Verify the engine against the public ground truth (`dataset/sample_output.csv`):
```bash
python code/main.py --evaluate_samples
```

### Run Automated Test Suite
Execute the comprehensive unit test suite covering identity resolution, policy enforcement, topological sorting, output validation, and custom forensic scenarios:
```bash
python -m unittest discover tests
```

---

## 4. Repository Structure

```text
├── code/
│   ├── main.py                     # Primary pipeline entry point
│   └── evaluation/
│       ├── evaluation_report.md    # Case, step, and sequence accuracy report
│       └── usage_report.md         # Token, model, and cost metrics
├── src/
│   ├── __init__.py
│   ├── data_loader.py              # CSV ingestion and normalization
│   ├── identity_resolution.py      # Current & historical identity graph
│   ├── evidence_ingestion.py       # SQL, JSON, Log, PDF, TXT parsers
│   ├── evidence_retrieval.py       # User-resource ownership graph
│   ├── policy_engine.py            # Deletion policy rules & action mappings
│   ├── temporal_state.py           # Cutoff evaluation & replication drift
│   ├── remediation_planner.py      # Ordered remediation & verifications
│   ├── step_ordering.py            # Strict phase & operation sorting
│   ├── deletion_audit.py           # Core orchestrator engine
│   ├── output_generator.py         # CSV serialization with JSON escaping
│   └── validate_output.py          # 20-point automated checklist
├── tests/
│   ├── test_identity_resolution.py
│   ├── test_policy_engine.py
│   ├── test_step_ordering.py
│   ├── test_output_validation.py
│   └── test_additional_cases.py    # 3 participant-created scenarios
├── config/
│   └── config.example.json         # Configuration schema
├── prompts/
│   └── evidence_analysis.md        # Forensic reasoning and prompt guide
├── evaluation/
│   ├── evaluation_report.md
│   └── usage_report.md
├── output.csv                      # Official 518-row prediction output
├── log.txt                         # Coding agent conversation transcript
├── requirements.txt
└── README.md
```

---

## 5. Submission Link

HackerRank Orchestrate — Ghost Data Still Exists:  
https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists
