"""Comprehensive output validator for Ghost Data Still Exists.
Enforces the 20-point compliance checklist.
"""

import os
import csv
import json
from typing import Dict, List, Any, Tuple


ALLOWED_STATUSES = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}
ALLOWED_PHASES = {"FINDING", "REMEDIATION", "VERIFICATION"}
ALLOWED_FINDING_OPS = {
    "REPORT_REMAINING_RECORD": "PRESENT",
    "REPORT_EXPOSED_PII": "PRESENT",
    "REPORT_ACTIVE_DATA_FLOW": "ACTIVE",
    "REPORT_RESTORE_RISK": "ACTIVE"
}
ALLOWED_REMEDIATION_OPS = {
    "DISABLE_DATA_FLOW": "DISABLED",
    "BLOCK_RESTORE": "BLOCKED",
    "DELETE_RECORD": "ABSENT",
    "REDACT_RECORD": "REDACTED",
    "ANONYMIZE_RECORD": "ANONYMIZED"
}
ALLOWED_VERIFICATION_OPS = {
    "VERIFY_RECORD_ABSENT": "ABSENT",
    "VERIFY_RECORD_PRESENT": "PRESENT",
    "VERIFY_RECORD_REDACTED": "REDACTED",
    "VERIFY_RECORD_ANONYMIZED": "ANONYMIZED",
    "VERIFY_DATA_FLOW_DISABLED": "DISABLED",
    "VERIFY_RESTORE_BLOCKED": "BLOCKED"
}


def validate_output_file(output_path: str = "output.csv", expected_case_count: int = 518) -> Tuple[bool, List[str]]:
    """Runs all 20 validation checks against output_path."""
    errors = []
    
    # 1. File exists
    if not os.path.exists(output_path):
        return False, [f"File {output_path} does not exist."]
    if os.path.getsize(output_path) == 0:
        return False, [f"File {output_path} is empty."]

    rows = []
    with open(output_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        
        # 2. Exact header
        if header != ["case_id", "deletion_status", "steps_json"]:
            errors.append(f"Header mismatch: expected ['case_id', 'deletion_status', 'steps_json'], got {header}")
            
        for row in reader:
            rows.append(row)

    # 3. Row count
    if len(rows) != expected_case_count:
        errors.append(f"Expected {expected_case_count} rows, got {len(rows)}")

    case_ids = [r[0] for r in rows if r]
    
    # 4. Duplicate case IDs
    if len(case_ids) != len(set(case_ids)):
        errors.append("Duplicate case_ids detected.")

    # 5. Sorting by case_id numeric index
    try:
        sorted_case_ids = sorted(case_ids, key=lambda x: int(x.split("_")[1]))
        if case_ids != sorted_case_ids:
            errors.append("Rows are not sorted by case_id.")
    except Exception as e:
        errors.append(f"Failed to check sorting: {e}")

    # Inspect each row
    for r_idx, row in enumerate(rows, 1):
        if len(row) != 3:
            errors.append(f"Row {r_idx} has {len(row)} columns instead of 3.")
            continue
            
        cid, status, steps_str = row
        
        # 6. Allowed status
        if status not in ALLOWED_STATUSES:
            errors.append(f"Row {r_idx} ({cid}): invalid status '{status}'")
            continue
            
        # 7. Valid JSON
        try:
            steps = json.loads(steps_str)
        except Exception as e:
            errors.append(f"Row {r_idx} ({cid}): invalid JSON in steps_json: {e}")
            continue
            
        if not isinstance(steps, list):
            errors.append(f"Row {r_idx} ({cid}): steps_json is not an array.")
            continue
            
        # 8. NOT_APPLICABLE has empty steps
        if status == "NOT_APPLICABLE":
            if len(steps) != 0:
                errors.append(f"Row {r_idx} ({cid}): NOT_APPLICABLE must have empty steps_json, got {len(steps)} steps.")
            continue
            
        # 9. COMPLETE cases only have VERIFICATION
        if status == "COMPLETE":
            for s in steps:
                if s.get("phase") != "VERIFICATION":
                    errors.append(f"Row {r_idx} ({cid}): COMPLETE case contains non-VERIFICATION step: {s}")
                if not s.get("evidence_id"):
                    errors.append(f"Row {r_idx} ({cid}): COMPLETE case verification step has empty evidence_id: {s}")

        # 10. INCOMPLETE cases
        if status == "INCOMPLETE":
            has_finding = any(s.get("phase") == "FINDING" for s in steps)
            has_remediation = any(s.get("phase") == "REMEDIATION" for s in steps)
            if not has_finding:
                errors.append(f"Row {r_idx} ({cid}): INCOMPLETE case missing FINDING steps.")
            if not has_remediation:
                errors.append(f"Row {r_idx} ({cid}): INCOMPLETE case missing REMEDIATION steps.")

        # 11. Step structure, numbering, phase ordering
        current_phase_rank = 0
        phase_map = {"FINDING": 1, "REMEDIATION": 2, "VERIFICATION": 3}
        
        for idx, s in enumerate(steps, 1):
            if s.get("step_no") != idx:
                errors.append(f"Row {r_idx} ({cid}): step {idx} has invalid step_no {s.get('step_no')}")
                
            phase = s.get("phase")
            if phase not in ALLOWED_PHASES:
                errors.append(f"Row {r_idx} ({cid}): invalid phase '{phase}'")
                continue
                
            rank = phase_map.get(phase, 0)
            if rank < current_phase_rank:
                errors.append(f"Row {r_idx} ({cid}): phase ordering violated: {phase} after earlier higher phase.")
            current_phase_rank = rank
            
            op = s.get("operation")
            state = s.get("state")
            
            if phase == "FINDING":
                if op not in ALLOWED_FINDING_OPS:
                    errors.append(f"Row {r_idx} ({cid}): invalid finding operation '{op}'")
                elif state != ALLOWED_FINDING_OPS[op]:
                    errors.append(f"Row {r_idx} ({cid}): finding operation '{op}' has unexpected state '{state}'")
                if not s.get("evidence_id"):
                    errors.append(f"Row {r_idx} ({cid}): finding step missing evidence_id: {s}")
                    
            elif phase == "REMEDIATION":
                if op not in ALLOWED_REMEDIATION_OPS:
                    errors.append(f"Row {r_idx} ({cid}): invalid remediation operation '{op}'")
                elif state != ALLOWED_REMEDIATION_OPS[op]:
                    errors.append(f"Row {r_idx} ({cid}): remediation operation '{op}' has unexpected state '{state}'")
                if s.get("evidence_id") != "":
                    errors.append(f"Row {r_idx} ({cid}): remediation step must have empty evidence_id, got '{s.get('evidence_id')}'")

            elif phase == "VERIFICATION":
                if op not in ALLOWED_VERIFICATION_OPS:
                    errors.append(f"Row {r_idx} ({cid}): invalid verification operation '{op}'")
                elif state != ALLOWED_VERIFICATION_OPS[op]:
                    errors.append(f"Row {r_idx} ({cid}): verification operation '{op}' has unexpected state '{state}'")
                if status == "INCOMPLETE" and s.get("evidence_id") != "":
                    errors.append(f"Row {r_idx} ({cid}): INCOMPLETE verification step must have empty evidence_id, got '{s.get('evidence_id')}'")

    is_valid = len(errors) == 0
    return is_valid, errors


if __name__ == "__main__":
    valid, errs = validate_output_file()
    if valid:
        print("[SUCCESS] All 20 validation checks passed!")
    else:
        print(f"[FAIL] Found {len(errs)} validation errors:")
        for e in errs[:20]:
            print("  *", e)
