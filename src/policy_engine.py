"""Policy engine module for Ghost Data Still Exists.
Applies deletion rules and determines required treatments and compliance states.
"""

from typing import Dict, Any, Tuple, Optional


# System ID mappings
SYSTEM_BY_PREFIX = {
    "account_": "account_service",
    "search_": "search_service",
    "support_": "support_platform",
    "analytics_": "analytics_platform",
    "export_": "export_service",
    "backup_": "backup_service",
    "data_flow_": "integration_service",
    "audit_record_": "security_service",
    "marketing_": "marketing_platform",
    "tombstone_": "identity_service",
    "object_": "object_storage",
    "legal_": "legal_retention"
}


# Default action per system
ACTION_BY_SYSTEM = {
    "account_service": "DELETE",
    "search_service": "DELETE",
    "export_service": "DELETE",
    "marketing_platform": "DELETE",
    "object_storage": "DELETE",
    "support_platform": "REDACT",
    "identity_service": "REDACT",
    "analytics_platform": "ANONYMIZE",
    "security_service": "RETAIN",
    "legal_retention": "RETAIN",
    "backup_service": "BLOCK",
    "integration_service": "DISABLE"
}


def infer_system_id(resource_id: str, default: str = "unknown") -> str:
    """Infers the canonical system_id from a resource_id."""
    for prefix, sys_id in SYSTEM_BY_PREFIX.items():
        if resource_id.startswith(prefix):
            return sys_id
    return default


def get_required_action(system_id: str) -> str:
    """Returns the required policy action for a system."""
    return ACTION_BY_SYSTEM.get(system_id, "DELETE")


def get_operation_for_action(action: str, phase: str, is_violation: bool = False) -> Tuple[str, str]:
    """Returns the appropriate (operation, state) pair given an action, phase, and violation status."""
    if phase == "FINDING":
        if action == "DISABLE":
            return "REPORT_ACTIVE_DATA_FLOW", "ACTIVE"
        elif action == "BLOCK":
            return "REPORT_RESTORE_RISK", "ACTIVE"
        elif action in ("REDACT", "ANONYMIZE"):
            return "REPORT_EXPOSED_PII", "PRESENT"
        else:
            return "REPORT_REMAINING_RECORD", "PRESENT"
            
    elif phase == "REMEDIATION":
        if action == "DISABLE":
            return "DISABLE_DATA_FLOW", "DISABLED"
        elif action == "BLOCK":
            return "BLOCK_RESTORE", "BLOCKED"
        elif action == "DELETE":
            return "DELETE_RECORD", "ABSENT"
        elif action == "REDACT":
            return "REDACT_RECORD", "REDACTED"
        elif action == "ANONYMIZE":
            return "ANONYMIZE_RECORD", "ANONYMIZED"
            
    elif phase == "VERIFICATION":
        if action == "DISABLE":
            return "VERIFY_DATA_FLOW_DISABLED", "DISABLED"
        elif action == "BLOCK":
            return "VERIFY_RESTORE_BLOCKED", "BLOCKED"
        elif action == "DELETE":
            return "VERIFY_RECORD_ABSENT", "ABSENT"
        elif action == "RETAIN":
            return "VERIFY_RECORD_PRESENT", "PRESENT"
        elif action == "REDACT":
            return "VERIFY_RECORD_REDACTED", "REDACTED"
        elif action == "ANONYMIZE":
            return "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"

    raise ValueError(f"Unknown action {action} and phase {phase}")
