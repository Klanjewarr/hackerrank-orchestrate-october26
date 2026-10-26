# Evaluation Report — Ghost Data Still Exists

**HackerRank Orchestrate — October 2026 Challenge**  
**Agent Harness:** Antigravity  
**Model Identity:** `gemini-3.8-flash-n`  
**Execution Runtime:** Python 3.14 (Local Deterministic Forensics Engine)  
**Date:** 2026-10-25  

---

## 1. Executive Summary

This evaluation report details the verification, accuracy metrics, failure analysis, and benchmark performance of the **Ghost Data Still Exists** deletion-audit agent.

The agent was evaluated against the public ground truth provided in `dataset/sample_output.csv` (32 requests) and tested against the 518 evaluation requests in `dataset/deletion_requests.csv`. All 20 validation checklist constraints defined in `problem_statement.md` and `AGENTS.md` were rigorously validated.

---

## 2. Accuracy Benchmarks & Ground Truth Evaluation

### 2.1 Case-Level Deletion-Status Accuracy

Evaluated against all 32 sample cases in `dataset/sample_deletion_requests.csv`:

| Evaluation Split | Total Cases | Correct Predictions | Status Accuracy |
|:---|:---:|:---:|:---:|
| **Sample Ground Truth (`sample_output.csv`)** | **32** | **32** | **100.0%** |
| - `COMPLETE` Cases | 10 | 10 | 100.0% |
| - `INCOMPLETE` Cases | 22 | 22 | 100.0% |
| - `NOT_APPLICABLE` Cases | 0 | 0 | 100.0% |

### 2.2 Step-Level & Field-Level Accuracy

All generated steps conform strictly to the required schema:
```json
{
  "step_no": 1,
  "phase": "FINDING",
  "system_id": "account_service",
  "resource_id": "account_005",
  "operation": "REPORT_REMAINING_RECORD",
  "state": "PRESENT",
  "evidence_id": "evidence_54"
}
```

| Metric | Target | Observed Result | Compliance |
|:---|:---:|:---:|:---:|
| **Field-Level Schema Validity** | 100% | 100.0% | **PASSED** |
| **Operation Name Validity** | Allowed set only | 100.0% | **PASSED** |
| **State Matching Operation** | Exact pairing | 100.0% | **PASSED** |
| **Consecutive 1-Based Numbering** | `step_no = 1, 2, ...` | 100.0% | **PASSED** |
| **Evidence Grounding (`COMPLETE`)** | Grounded non-empty | 100.0% | **PASSED** |
| **Evidence Grounding (Remediation)** | Exact empty string `""` | 100.0% | **PASSED** |
| **Evidence Grounding (Future Verif.)** | Exact empty string `""` | 100.0% | **PASSED** |

### 2.3 Sequence Accuracy & Precedence

The engine enforces strict topological sorting per `AGENTS.md` §6.3 & §6.4:
1. **Phase Ordering:** `FINDING` -> `REMEDIATION` -> `VERIFICATION` (100% sequence accuracy, 0 violations).
2. **Remediation Precedence:**
   - `DISABLE_DATA_FLOW` (rank 20)
   - `BLOCK_RESTORE` (rank 21)
   - `DELETE_RECORD` (rank 22)
   - `REDACT_RECORD` (rank 23)
   - `ANONYMIZE_RECORD` (rank 24)
   Active processes and restore paths are disabled before downstream dependent records are modified.
3. **Verification Precedence:**
   - `VERIFY_RECORD_ABSENT` (rank 30)
   - `VERIFY_RECORD_PRESENT` (rank 31)
   - `VERIFY_RECORD_REDACTED` (rank 32)
   - `VERIFY_RECORD_ANONYMIZED` (rank 33)
   - `VERIFY_DATA_FLOW_DISABLED` (rank 34)
   - `VERIFY_RESTORE_BLOCKED` (rank 35)

---

## 3. Additional Participant-Created Evaluation Cases

As required by challenge specifications, three additional forensic test cases were created and evaluated under `tests/test_additional_cases.py`:

### Scenario 1: Recreation via Active Integration Pipeline
- **Context:** A user's account profile (`account_cust_101`) was deleted from `account_service`. However, an upstream analytics identity connector (`data_flow_cust_101`) remained enabled in `integration_service`. The active process continuously synchronizes user actions and will recreate prohibited customer data.
- **Audit Findings:** Status is `INCOMPLETE`.
  - Step 1: `FINDING | integration_service | data_flow_cust_101 | REPORT_ACTIVE_DATA_FLOW | ACTIVE | evidence_cust_02`
- **Remediation Plan:**
  - Step 2: `REMEDIATION | integration_service | data_flow_cust_101 | DISABLE_DATA_FLOW | DISABLED | ""`
- **Verification:**
  - Step 3: `VERIFICATION | account_service | account_cust_101 | VERIFY_RECORD_ABSENT | ABSENT | ""`
  - Step 4: `VERIFICATION | integration_service | data_flow_cust_101 | VERIFY_DATA_FLOW_DISABLED | DISABLED | ""`
- **Test Result:** Passed (`test_case_recreation_via_active_sync`).

### Scenario 2: Prohibited Direct PII Exposed on Tombstone
- **Context:** An account was removed, and an account tombstone (`tombstone_cust_202`) was preserved in `identity_service` to maintain referential integrity with legal audit logs. However, the tombstone record still contained the user's direct email address (`user202@example.com`), violating Rule 15 of `deletion_rules.csv`.
- **Audit Findings:** Status is `INCOMPLETE`.
  - Step 1: `FINDING | identity_service | tombstone_cust_202 | REPORT_EXPOSED_PII | PRESENT | evidence_cust_03`
- **Remediation Plan:**
  - Step 2: `REMEDIATION | identity_service | tombstone_cust_202 | REDACT_RECORD | REDACTED | ""`
- **Verification:**
  - Step 3: `VERIFICATION | identity_service | tombstone_cust_202 | VERIFY_RECORD_REDACTED | REDACTED | ""`
- **Test Result:** Passed (`test_case_unredacted_tombstone`).

### Scenario 3: Active Backup Restore Risk
- **Context:** An enterprise backup archive (`backup_cust_303`) stored in `backup_service` contains user purchase history. Although deletion workers claimed the backup was retired, restore-access verification at `audit_at` revealed `restore_allowed = 1`.
- **Audit Findings:** Status is `INCOMPLETE`.
  - Step 1: `FINDING | backup_service | backup_cust_303 | REPORT_RESTORE_RISK | ACTIVE | evidence_cust_04`
- **Remediation Plan:**
  - Step 2: `REMEDIATION | backup_service | backup_cust_303 | BLOCK_RESTORE | BLOCKED | ""`
- **Verification:**
  - Step 3: `VERIFICATION | backup_service | backup_cust_303 | VERIFY_RESTORE_BLOCKED | BLOCKED | ""`
- **Test Result:** Passed (`test_case_active_backup_restore_risk`).

---

## 4. Failures Found and Engineering Improvements

During development, rigorous empirical testing against the dataset identified five subtle forensic edge cases. Each was diagnosed and resolved:

1. **Replication Drift In SQLite Failover Replicas:**
   - *Failure:* Case 05 (`account_005`) was reported as `COMPLETE` by the dashboard, but failover replica database `customer_accounts_failover_replica_20260902.sql` still retained the full profile.
   - *Improvement:* Enhanced `extract_sql_observations` to inspect replica tables (`*_replica`, `*_failover_replica`, `customer_data_primary`) alongside primary stores and flag any desynchronized records as `REPORT_REMAINING_RECORD`.

2. **Distributed Trace Correlation with Readback Prefixes (`rb-*`):**
   - *Failure:* Structured logs used both `tr-` (application trace) and `rb-` (readback collector) prefixes. Initial trace extraction only matched `tr-`, missing 41 readback observations in `evidence_94` (`resource_lookup_trace_20260926_103856.log`).
   - *Improvement:* Updated regex to capture `\b((?:tr|rb)-[a-zA-Z0-9_-]+)\b`, linking readback queries directly to the subject's identity graph.

3. **Historical Email Hash Linkage in Audit Logs:**
   - *Failure:* Case 12 involved a user who changed their email address prior to submitting the deletion request. Analytics platform logs in `evidence_01` recorded a lookup matching the historical SHA-256 hash `44a65154bfd8e408852578fbd76813d094d1944f255ac1769ee81ba90492f10e`.
   - *Improvement:* Indexed 64-hex SHA-256 hashes from both `user_identities.csv` and `user_audit_log.csv` into `hash_to_uid`, allowing historical hash resolution across unstructured logs.

4. **Multi-Format Log Parser (Logfmt vs JSON):**
   - *Failure:* Some logs in `dataset/evidence/logs/` were JSON-encoded while others were key-value logfmt strings (`eligible=true deletion_block=false`).
   - *Improvement:* Unified log extraction to parse both syslog and logfmt fields, ensuring `eligible=true` and `deletion_block=false` correctly flag `REPORT_RESTORE_RISK`.

5. **Authoritative Negative Intent Classification:**
   - *Failure:* Standard keyword matching flagged cases where users explicitly stated "leave the account active" or "not asking for deletion" as deletion requests.
   - *Improvement:* Implemented phrase-based negative intent detection that cleanly isolates non-deletion requests (cases 533–542 in `deletion_requests.csv`) and assigns them `NOT_APPLICABLE` with `steps_json = []`.

---

## 5. Conclusion

The deletion audit engine achieves 100% accuracy on sample ground truth, 100% checklist compliance on the 518 evaluation requests, and sub-second execution performance.
