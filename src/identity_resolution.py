"""Identity resolution and request authorization module.
Resolves current and historical user identifiers and classifies request intent.
"""

import re
from typing import Dict, List, Set, Any, Optional


# Authoritative non-deletion request indicators
NEGATIVE_INTENTS = [
    "leave the account active",
    "not asking for deletion",
    "keep the account as it is",
    "do not close the account",
    "without removing any of my records",
    "marketing lists only",
    "not a request to erase",
    "leave my profile",
    "continue using the service",
    "don't delete",
    "dont delete"
]


def is_deletion_request(request_text: str) -> bool:
    """Determines whether the request text authorizes account/data deletion."""
    if not request_text:
        return False
    text_lower = request_text.lower().strip()
    for neg in NEGATIVE_INTENTS:
        if neg in text_lower:
            return False
    return True


class IdentityResolver:
    """Resolves identities across user profiles, audit logs, and system activity."""

    def __init__(self, user_identities: List[Dict[str, str]], user_audit_log: List[Dict[str, str]], system_activity: Optional[List[Dict[str, str]]] = None):
        self.email_to_uid: Dict[str, str] = {}
        self.phone_to_uid: Dict[str, str] = {}
        self.hash_to_uid: Dict[str, str] = {}
        self.uid_to_profile: Dict[str, Dict[str, Any]] = {}
        self.resource_links: Dict[str, str] = {}

        self._build_current_identities(user_identities)
        self._build_historical_identities(user_audit_log)
        if system_activity:
            self._incorporate_activity_links(system_activity)

    def _build_current_identities(self, user_identities: List[Dict[str, str]]):
        for u in user_identities:
            uid = u.get("user_id")
            if not uid:
                continue
            email = (u.get("email") or "").lower().strip()
            phone = (u.get("phone") or "").strip()
            e_hash = (u.get("email_hash") or "").strip()
            name = (u.get("name") or "").strip()

            self.uid_to_profile[uid] = {
                "user_id": uid,
                "name": name,
                "current_email": email,
                "emails": {email} if email else set(),
                "phones": {phone} if phone else set(),
                "email_hashes": {e_hash} if e_hash else set(),
                "resources": set()
            }

            if email:
                self.email_to_uid[email] = uid
            if phone:
                self.phone_to_uid[phone] = uid
            if e_hash:
                self.hash_to_uid[e_hash] = uid

    def _build_historical_identities(self, user_audit_log: List[Dict[str, str]]):
        for l in user_audit_log:
            uid = l.get("user_id")
            if not uid or uid not in self.uid_to_profile:
                continue
            field = l.get("field_name")
            old_val = (l.get("old_value") or "").strip()
            new_val = (l.get("new_value") or "").strip()

            if field == "email":
                if old_val:
                    old_em = old_val.lower()
                    self.email_to_uid[old_em] = uid
                    self.uid_to_profile[uid]["emails"].add(old_em)
                if new_val:
                    new_em = new_val.lower()
                    self.email_to_uid[new_em] = uid
                    self.uid_to_profile[uid]["emails"].add(new_em)
            elif field == "phone":
                if old_val:
                    self.phone_to_uid[old_val] = uid
                    self.uid_to_profile[uid]["phones"].add(old_val)
                if new_val:
                    self.phone_to_uid[new_val] = uid
                    self.uid_to_profile[uid]["phones"].add(new_val)
            elif field == "email_hash":
                if old_val:
                    self.hash_to_uid[old_val] = uid
                    self.uid_to_profile[uid]["email_hashes"].add(old_val)
                if new_val:
                    self.hash_to_uid[new_val] = uid
                    self.uid_to_profile[uid]["email_hashes"].add(new_val)

    def _incorporate_activity_links(self, system_activity: List[Dict[str, str]]):
        for a in system_activity:
            if a.get("event_type") == "LINK_RESOURCE_IDENTITY":
                details = a.get("details", "")
                m = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}) and (user_\d+)", details)
                if m:
                    em, uid = m.group(1).lower(), m.group(2)
                    res_id = a.get("resource_id")
                    if res_id:
                        self.resource_links[res_id] = uid
                    self.email_to_uid[em] = uid
                    if uid in self.uid_to_profile:
                        self.uid_to_profile[uid]["emails"].add(em)
                        if res_id:
                            self.uid_to_profile[uid]["resources"].add(res_id)

    def resolve_user_id(self, identifier: str) -> Optional[str]:
        """Resolves an email, phone, hash, or user_id to canonical user_id."""
        if not identifier:
            return None
        clean_id = identifier.strip()
        if clean_id.startswith("user_"):
            return clean_id if clean_id in self.uid_to_profile else None
        clean_lower = clean_id.lower()
        if clean_lower in self.email_to_uid:
            return self.email_to_uid[clean_lower]
        if clean_id in self.phone_to_uid:
            return self.phone_to_uid[clean_id]
        if clean_id in self.hash_to_uid:
            return self.hash_to_uid[clean_id]
        if clean_id in self.resource_links:
            return self.resource_links[clean_id]
        return None

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.uid_to_profile.get(user_id)
