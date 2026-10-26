"""Step ordering module for Ghost Data Still Exists.
Enforces strict phase, operation, and resource order with 1-based sequential step numbers.
"""

from typing import List, Dict, Any


PHASE_ORDER = {
    "FINDING": 1,
    "REMEDIATION": 2,
    "VERIFICATION": 3
}


OPERATION_ORDER = {
    # Findings
    "REPORT_REMAINING_RECORD": 10,
    "REPORT_EXPOSED_PII": 11,
    "REPORT_ACTIVE_DATA_FLOW": 12,
    "REPORT_RESTORE_RISK": 13,
    
    # Remediation
    "DISABLE_DATA_FLOW": 20,
    "BLOCK_RESTORE": 21,
    "DELETE_RECORD": 22,
    "REDACT_RECORD": 23,
    "ANONYMIZE_RECORD": 24,
    
    # Verification
    "VERIFY_RECORD_ABSENT": 30,
    "VERIFY_RECORD_PRESENT": 31,
    "VERIFY_RECORD_REDACTED": 32,
    "VERIFY_RECORD_ANONYMIZED": 33,
    "VERIFY_DATA_FLOW_DISABLED": 34,
    "VERIFY_RESTORE_BLOCKED": 35
}


def step_sort_key(step: Dict[str, Any]):
    """Generates a sorting key for a step dictionary."""
    phase_rank = PHASE_ORDER.get(step.get("phase", ""), 99)
    op_rank = OPERATION_ORDER.get(step.get("operation", ""), 99)
    sys_id = step.get("system_id", "")
    res_id = step.get("resource_id", "")
    return (phase_rank, op_rank, sys_id, res_id)


def sort_and_renumber_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sorts steps by phase, operation, system_id, resource_id and assigns consecutive 1-based step_no."""
    sorted_steps = sorted(steps, key=step_sort_key)
    result = []
    for idx, s in enumerate(sorted_steps, 1):
        step_dict = {
            "step_no": idx,
            "phase": s["phase"],
            "system_id": s["system_id"],
            "resource_id": s["resource_id"],
            "operation": s["operation"],
            "state": s["state"],
            "evidence_id": s.get("evidence_id", "")
        }
        result.append(step_dict)
    return result
