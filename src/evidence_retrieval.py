"""Evidence retrieval and user-resource graph resolution module.
"""

from typing import Dict, List, Set, Tuple, Optional
from src.identity_resolution import IdentityResolver
from src.evidence_ingestion import EvidenceObservation
from src.policy_engine import infer_system_id


class ResourceGraph:
    """Maintains and queries the ownership graph between users and system resources."""

    def __init__(
        self,
        resolver: IdentityResolver,
        observations: List[EvidenceObservation],
        system_activity: Optional[List[Dict[str, str]]] = None
    ):
        self.resolver = resolver
        self.user_to_resources: Dict[str, Set[Tuple[str, str]]] = {}
        self.resource_to_user: Dict[str, str] = {}
        self.resource_to_system: Dict[str, str] = {}

        self._index_observations(observations)
        if system_activity:
            self._index_system_activity(system_activity)
        self._add_default_accounts()

    def _index_observations(self, observations: List[EvidenceObservation]):
        for ob in observations:
            res_id = ob.resource_id
            sys_id = ob.system_id
            if sys_id == "unknown":
                sys_id = infer_system_id(res_id)
            self.resource_to_system[res_id] = sys_id
            
            # Resolve user
            uid = ob.user_id
            if not uid and ob.email:
                uid = self.resolver.resolve_user_id(ob.email)
            if uid:
                self.resource_to_user[res_id] = uid
                if uid not in self.user_to_resources:
                    self.user_to_resources[uid] = set()
                self.user_to_resources[uid].add((sys_id, res_id))

    def _index_system_activity(self, system_activity: List[Dict[str, str]]):
        for act in system_activity:
            res_id = act.get("resource_id")
            if not res_id:
                continue
            canonical_sys = infer_system_id(res_id)
            tgt_sys = canonical_sys if canonical_sys != "unknown" else (act.get("target_system") or "unknown")
            if res_id not in self.resource_to_system:
                self.resource_to_system[res_id] = tgt_sys
                
            # Check if this activity belongs to a known resource link
            if res_id in self.resource_to_user:
                uid = self.resource_to_user[res_id]
                self.user_to_resources[uid].add((tgt_sys, res_id))

    def _add_default_accounts(self):
        for uid in self.resolver.uid_to_profile:
            existing = self.user_to_resources.get(uid, set())
            has_account = any(s == "account_service" for s, r in existing)
            if has_account:
                continue
            try:
                num = int(uid.split("_")[1])
                acc_id = f"account_{num:03d}"
                if acc_id not in self.resource_to_system:
                    self.resource_to_system[acc_id] = "account_service"
                if acc_id not in self.resource_to_user:
                    self.resource_to_user[acc_id] = uid
                    if uid not in self.user_to_resources:
                        self.user_to_resources[uid] = set()
                    self.user_to_resources[uid].add(("account_service", acc_id))
            except Exception:
                pass

    def get_resources_for_user(self, user_id: str) -> List[Tuple[str, str]]:
        """Returns sorted list of (system_id, resource_id) belonging to user_id."""
        res_set = self.user_to_resources.get(user_id, set())
        # Deduplicate and sort by system_id, resource_id
        return sorted(list(res_set), key=lambda x: (x[0], x[1]))
