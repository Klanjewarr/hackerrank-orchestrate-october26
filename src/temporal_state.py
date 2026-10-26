"""Temporal evidence evaluation and state reconstruction module.
Evaluates evidence strictly at or before audit_at cutoff time.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from src.evidence_ingestion import EvidenceObservation
from src.policy_engine import get_required_action, infer_system_id


def parse_iso(ts_str: str) -> datetime:
    """Parses an ISO-8601 timestamp string safely to UTC datetime."""
    clean = ts_str.replace("Z", "+00:00")
    return datetime.fromisoformat(clean)


class ResourceTemporalEvaluator:
    """Evaluates the compliant/non-compliant state of a resource at audit_at."""

    def __init__(self, observations: List[EvidenceObservation], evidence_manifest: Optional[List[Dict[str, str]]] = None):
        # Group observations by resource_id
        self.res_observations: Dict[str, List[EvidenceObservation]] = {}
        for ob in observations:
            if ob.resource_id not in self.res_observations:
                self.res_observations[ob.resource_id] = []
            self.res_observations[ob.resource_id].append(ob)
            
        # Sort each resource's observations by captured_at ascending
        for res_id, obs_list in self.res_observations.items():
            obs_list.sort(key=lambda o: parse_iso(o.captured_at))
            
        # Build system coverage map from manifest
        self.system_coverage: List[Dict[str, Any]] = []
        if evidence_manifest:
            for f in evidence_manifest:
                fid = f["file_id"]
                fp = f["file_path"]
                capt = f["captured_at"]
                systems = set()
                
                if any(k in fp for k in ["customer_accounts", "failover_replica", "customer_data_inventory", "customer_data_primary", "read_replica", "regional_replicas", "reporting_replica"]):
                    systems.add("account_service")
                if "service_resource_export" in fp:
                    systems.update(["account_service", "analytics_platform", "support_platform", "integration_service", "backup_service", "security_service", "search_service", "export_service"])
                if "customer_data_snapshot_bundle" in fp:
                    systems.update(["account_service", "analytics_platform", "support_platform", "integration_service", "backup_service", "security_service", "identity_service"])
                if "resource_lookup_trace" in fp:
                    systems.update(["account_service", "analytics_platform", "support_platform", "integration_service", "search_service", "security_service"])
                if "customer_search" in fp:
                    systems.add("search_service")
                if "customer_analytics" in fp:
                    systems.add("analytics_platform")
                if "support_replica" in fp:
                    systems.add("support_platform")
                if "connector_configurations" in fp:
                    systems.add("integration_service")
                if "customer_export" in fp:
                    systems.add("export_service")
                if "customer_account_handover" in fp:
                    systems.update(["account_service", "search_service", "support_platform", "export_service"])
                    
                self.system_coverage.append({
                    "file_id": fid,
                    "file_path": fp,
                    "captured_at": capt,
                    "systems": systems
                })
            self.system_coverage.sort(key=lambda x: parse_iso(x["captured_at"]))

    def get_coverage_evidence_for_system(self, system_id: str, audit_at: str) -> str:
        """Finds the latest evidence file captured at or before audit_at covering system_id."""
        audit_dt = parse_iso(audit_at)
        valid = [c for c in self.system_coverage if system_id in c["systems"] and parse_iso(c["captured_at"]) <= audit_dt]
        return valid[-1]["file_id"] if valid else ""

    def evaluate_resource_at_time(
        self,
        system_id: str,
        resource_id: str,
        audit_at: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reconstructs the state of a resource at audit_at cutoff."""
        audit_dt = parse_iso(audit_at)
        required_action = get_required_action(system_id)
        
        # Get all observations up to audit_at
        all_obs = self.res_observations.get(resource_id, [])
        valid_obs = [o for o in all_obs if parse_iso(o.captured_at) <= audit_dt]
        
        # Check replication drift or remaining record in any replica/table
        rep_drift = [o for o in valid_obs if o.observed_state == "PRESENT" and ("replica" in str(o.details).lower() or "failover" in str(o.details).lower())]
        latest_ob = valid_obs[-1] if valid_obs else None
        
        if not valid_obs:
            # If no direct evidence of resource at or before audit_at, it was deleted/absent
            coverage_ev = self.get_coverage_evidence_for_system(system_id, audit_at)
            if required_action == "DELETE":
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": True,
                    "evidence_id": coverage_ev,
                    "state": "ABSENT"
                }
            elif required_action == "RETAIN":
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": True,
                    "evidence_id": coverage_ev,
                    "state": "PRESENT"
                }
            else:
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": True,
                    "evidence_id": coverage_ev,
                    "state": "ABSENT"
                }
                
        # If there is replica drift (primary absent, replica present)
        if rep_drift and required_action == "DELETE":
            drift_ob = rep_drift[-1]
            return {
                "system_id": system_id,
                "resource_id": resource_id,
                "is_compliant": False,
                "violation_type": "REMAINING_RECORD",
                "evidence_id": drift_ob.file_id,
                "state": "PRESENT"
            }
            
        evidence_id = latest_ob.file_id
        state = latest_ob.observed_state

        # Apply policy evaluation
        if required_action == "DELETE":
            if state == "ABSENT":
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": True,
                    "evidence_id": evidence_id,
                    "state": "ABSENT"
                }
            else:
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": False,
                    "violation_type": "REMAINING_RECORD",
                    "evidence_id": evidence_id,
                    "state": "PRESENT"
                }
                
        elif required_action == "REDACT":
            if latest_ob.has_pii or state == "PRESENT":
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": False,
                    "violation_type": "EXPOSED_PII",
                    "evidence_id": evidence_id,
                    "state": "PRESENT"
                }
            else:
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": True,
                    "evidence_id": evidence_id,
                    "state": "REDACTED"
                }
                
        elif required_action == "ANONYMIZE":
            if latest_ob.has_pii or state == "PRESENT":
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": False,
                    "violation_type": "EXPOSED_PII",
                    "evidence_id": evidence_id,
                    "state": "PRESENT"
                }
            else:
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": True,
                    "evidence_id": evidence_id,
                    "state": "ANONYMIZED"
                }
                
        elif required_action == "RETAIN":
            return {
                "system_id": system_id,
                "resource_id": resource_id,
                "is_compliant": True,
                "evidence_id": evidence_id,
                "state": "PRESENT"
            }
            
        elif required_action == "DISABLE":
            if state == "ACTIVE":
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": False,
                    "violation_type": "ACTIVE_DATA_FLOW",
                    "evidence_id": evidence_id,
                    "state": "ACTIVE"
                }
            else:
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": True,
                    "evidence_id": evidence_id,
                    "state": "DISABLED"
                }
                
        elif required_action == "BLOCK":
            if state == "ACTIVE":
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": False,
                    "violation_type": "RESTORE_RISK",
                    "evidence_id": evidence_id,
                    "state": "ACTIVE"
                }
            else:
                return {
                    "system_id": system_id,
                    "resource_id": resource_id,
                    "is_compliant": True,
                    "evidence_id": evidence_id,
                    "state": "BLOCKED"
                }

        return {
            "system_id": system_id,
            "resource_id": resource_id,
            "is_compliant": True,
            "evidence_id": evidence_id,
            "state": state
        }
