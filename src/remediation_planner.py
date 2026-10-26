"""Remediation planner and verification step generator module.
"""

from typing import List, Dict, Any
from src.policy_engine import get_required_action, get_operation_for_action
from src.step_ordering import sort_and_renumber_steps


def plan_remediation_and_verification(
    case_id: str,
    evaluations: List[Dict[str, Any]],
    is_complete: bool
) -> List[Dict[str, Any]]:
    """Constructs the findings, remediations, and verification steps for a case."""
    steps = []

    if is_complete:
        # COMPLETE case: only evidence-backed verification steps proving the state at audit_at
        for ev in evaluations:
            sys_id = ev["system_id"]
            res_id = ev["resource_id"]
            act = get_required_action(sys_id)
            op, state = get_operation_for_action(act, "VERIFICATION")
            
            steps.append({
                "phase": "VERIFICATION",
                "system_id": sys_id,
                "resource_id": res_id,
                "operation": op,
                "state": state,
                "evidence_id": ev.get("evidence_id", "")
            })
    else:
        # INCOMPLETE case:
        # 1. Findings (citing participant-visible evidence)
        violating_evals = [ev for ev in evaluations if not ev.get("is_compliant", True)]
        for ev in violating_evals:
            sys_id = ev["system_id"]
            res_id = ev["resource_id"]
            act = get_required_action(sys_id)
            op, state = get_operation_for_action(act, "FINDING", is_violation=True)
            
            steps.append({
                "phase": "FINDING",
                "system_id": sys_id,
                "resource_id": res_id,
                "operation": op,
                "state": state,
                "evidence_id": ev.get("evidence_id", "")
            })

        # 2. Remediation steps (ordered, evidence_id="")
        for ev in violating_evals:
            sys_id = ev["system_id"]
            res_id = ev["resource_id"]
            act = get_required_action(sys_id)
            op, state = get_operation_for_action(act, "REMEDIATION")
            
            steps.append({
                "phase": "REMEDIATION",
                "system_id": sys_id,
                "resource_id": res_id,
                "operation": op,
                "state": state,
                "evidence_id": ""
            })

        # 3. Post-remediation verification checks (evidence_id="")
        for ev in evaluations:
            sys_id = ev["system_id"]
            res_id = ev["resource_id"]
            act = get_required_action(sys_id)
            op, state = get_operation_for_action(act, "VERIFICATION")
            
            steps.append({
                "phase": "VERIFICATION",
                "system_id": sys_id,
                "resource_id": res_id,
                "operation": op,
                "state": state,
                "evidence_id": ""
            })

    return sort_and_renumber_steps(steps)
