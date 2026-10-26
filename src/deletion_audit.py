"""Core deletion audit engine for Ghost Data Still Exists.
"""

from typing import Dict, List, Any, Tuple
from src.identity_resolution import IdentityResolver, is_deletion_request
from src.evidence_retrieval import ResourceGraph
from src.temporal_state import ResourceTemporalEvaluator
from src.remediation_planner import plan_remediation_and_verification


class DeletionAuditEngine:
    """Executes deletion audit evaluation across all requests."""

    def __init__(
        self,
        resolver: IdentityResolver,
        resource_graph: ResourceGraph,
        temporal_evaluator: ResourceTemporalEvaluator
    ):
        self.resolver = resolver
        self.resource_graph = resource_graph
        self.temporal_evaluator = temporal_evaluator

    def audit_request(self, request: Dict[str, str]) -> Tuple[str, str, List[Dict[str, Any]]]:
        """Audits a single deletion request row."""
        case_id = request["case_id"]
        email = request.get("email", "").strip()
        audit_at = request["audit_at"]
        request_text = request.get("request_text", "")

        # 1. Determine request authorization
        if not is_deletion_request(request_text):
            return case_id, "NOT_APPLICABLE", []

        # 2. Resolve user identity
        uid = self.resolver.resolve_user_id(email)
        if not uid:
            # Fallback check
            return case_id, "NOT_APPLICABLE", []

        # 3. Retrieve relevant resources for this user
        resources = self.resource_graph.get_resources_for_user(uid)
        if not resources:
            # Check default account
            num = int(uid.split("_")[1])
            resources = [("account_service", f"account_{num:03d}")]

        # 4. Evaluate each resource at audit_at
        evaluations = []
        is_all_compliant = True
        
        for sys_id, res_id in resources:
            eval_res = self.temporal_evaluator.evaluate_resource_at_time(sys_id, res_id, audit_at, uid)
            evaluations.append(eval_res)
            if not eval_res.get("is_compliant", True):
                is_all_compliant = False

        status = "COMPLETE" if is_all_compliant else "INCOMPLETE"

        # 5. Generate ordered findings, remediations, and verification steps
        steps = plan_remediation_and_verification(case_id, evaluations, is_complete=is_all_compliant)

        return case_id, status, steps
