"""Evidence ingestion module for Ghost Data Still Exists.
Parses all participant evidence formats (JSON, SQL, Logs, TXT, PDF, Images).
"""

import os
import re
import csv
import json
import sqlite3
from typing import Dict, List, Any, Optional
from pypdf import PdfReader


class EvidenceObservation:
    """Represents a discrete state observation of a resource in evidence."""

    def __init__(
        self,
        file_id: str,
        captured_at: str,
        system_id: str,
        resource_id: str,
        observed_state: str,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        has_pii: bool = False,
        details: Optional[Dict[str, Any]] = None
    ):
        self.file_id = file_id
        self.captured_at = captured_at
        self.system_id = system_id
        self.resource_id = resource_id
        self.observed_state = observed_state # PRESENT, ABSENT, REDACTED, ANONYMIZED, ACTIVE, DISABLED, BLOCKED
        self.user_id = user_id
        self.email = email.lower() if email else None
        self.has_pii = has_pii
        self.details = details or {}


def extract_pdf_observations(file_id: str, captured_at: str, full_path: str, email_to_uid: Dict[str, str]) -> List[EvidenceObservation]:
    """Extracts text observations from PDF files."""
    obs = []
    if not full_path.endswith(".pdf"):
        return obs
    try:
        reader = PdfReader(full_path)
        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        
        # Check delivery correction attachment
        if "delivery_correction_attachment" in full_path:
            m_em = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", text)
            em = m_em.group(1).lower() if m_em else None
            uid = email_to_uid.get(em) if em else None
            obs.append(EvidenceObservation(
                file_id=file_id,
                captured_at=captured_at,
                system_id="support_platform",
                resource_id="support_001",
                observed_state="PRESENT",
                user_id=uid,
                email=em,
                has_pii=True,
                details={"type": "pdf_attachment", "text_excerpt": text[:200]}
            ))
    except Exception:
        pass
    return obs


def extract_txt_observations(file_id: str, captured_at: str, full_path: str, email_to_uid: Dict[str, str]) -> List[EvidenceObservation]:
    """Extracts observations from plain-text handover notes."""
    obs = []
    if not full_path.endswith(".txt"):
        return obs
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line_str = line.strip()
                if line_str.startswith("- "):
                    parts = [p.strip() for p in line_str[2:].split("|")]
                    if len(parts) >= 6:
                        ts, sys_name, res_id, category, status, sub_ref = parts[:6]
                        em = sub_ref.lower() if "@" in sub_ref else None
                        uid = sub_ref if sub_ref.startswith("user_") else (email_to_uid.get(em) if em else None)
                        
                        # Map status to state and pii
                        if status == "NOT_FOUND":
                            state = "ABSENT"
                            has_pii = False
                        elif status == "ANONYMIZED":
                            state = "ANONYMIZED"
                            has_pii = False
                        elif status == "REDACTED":
                            state = "REDACTED"
                            has_pii = False
                        elif status == "DISABLED":
                            state = "DISABLED"
                            has_pii = False
                        elif status == "BLOCKED":
                            state = "BLOCKED"
                            has_pii = False
                        elif status == "ACTIVE":
                            state = "ACTIVE"
                            has_pii = bool(em or uid)
                        elif status == "IDENTIFIABLE":
                            state = "PRESENT"
                            has_pii = True
                        elif status == "FOUND":
                            state = "PRESENT"
                            has_pii = True if sys_name != "security_service" else False
                        else:
                            state = "PRESENT"
                            has_pii = True
                            
                        obs.append(EvidenceObservation(
                            file_id=file_id,
                            captured_at=captured_at,
                            system_id=sys_name,
                            resource_id=res_id,
                            observed_state=state,
                            user_id=uid,
                            email=em,
                            has_pii=has_pii,
                            details={"category": category, "status": status, "raw_line": line_str}
                        ))
    except Exception:
        pass
    return obs


def extract_json_observations(file_id: str, captured_at: str, full_path: str, email_to_uid: Dict[str, str]) -> List[EvidenceObservation]:
    """Extracts observations from JSON files (bundles, exports, reports)."""
    obs = []
    if not full_path.endswith(".json"):
        return obs
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)

        if "service_exports" in data:
            exports = data["service_exports"]
            for sname, sdata in exports.items():
                for subk, items in sdata.items():
                    for item in items:
                        res_id = item.get("resource_id")
                        if not res_id:
                            continue
                        uid = item.get("customer_reference") or item.get("subject_reference") or item.get("user_id") or item.get("subject_selector")
                        em = item.get("email") or item.get("customer_email") or item.get("owner_email") or item.get("requester_email")
                        if not uid and em and em.lower() in email_to_uid:
                            uid = email_to_uid[em.lower()]
                            
                        status_code = item.get("status_code")
                        enabled = item.get("enabled")
                        restore_allowed = item.get("restore_allowed")
                        
                        if status_code == 404:
                            state = "ABSENT"
                            has_pii = False
                        elif enabled is not None:
                            state = "ACTIVE" if enabled else "DISABLED"
                            has_pii = bool(em or uid)
                        elif restore_allowed is not None:
                            state = "ACTIVE" if restore_allowed else "BLOCKED"
                            has_pii = bool(em or uid)
                        elif sname == "analytics_platform":
                            has_direct_pii = bool(item.get("email") or item.get("phone") or item.get("email_hash"))
                            state = "PRESENT" if has_direct_pii else "ANONYMIZED"
                            has_pii = has_direct_pii
                        elif sname == "support_platform":
                            has_direct_pii = bool(item.get("requester_email") or item.get("requester_name") or item.get("requester_phone"))
                            state = "PRESENT" if has_direct_pii else "REDACTED"
                            has_pii = has_direct_pii
                        elif sname == "security_service":
                            state = "PRESENT"
                            has_pii = False
                        else:
                            state = "PRESENT"
                            has_pii = True
                            
                        obs.append(EvidenceObservation(
                            file_id=file_id,
                            captured_at=captured_at,
                            system_id=sname,
                            resource_id=res_id,
                            observed_state=state,
                            user_id=uid,
                            email=em,
                            has_pii=has_pii,
                            details=item
                        ))

        elif "snapshots" in data:
            for snap in data["snapshots"]:
                store = snap.get("data_store", "unknown")
                for r in snap.get("records", []):
                    res_id = r.get("resource_id")
                    if not res_id:
                        continue
                    uid = r.get("customer_reference") or r.get("subject_reference") or r.get("user_id") or r.get("subject_selector") or r.get("subject_selector")
                    em = r.get("email") or r.get("owner_email") or r.get("requester_email") or r.get("customer_email")
                    doc = r.get("document", {})
                    if isinstance(doc, dict):
                        em = em or doc.get("email")
                        uid = uid or doc.get("customer_reference")
                    if not uid and em and em.lower() in email_to_uid:
                        uid = email_to_uid[em.lower()]
                        
                    if store == "analytics_platform":
                        has_direct_pii = bool(r.get("email") or r.get("phone") or r.get("email_hash"))
                        state = "PRESENT" if has_direct_pii else "ANONYMIZED"
                        has_pii = has_direct_pii
                    elif store == "identity_service":
                        has_direct_pii = bool(r.get("email") or r.get("phone") or r.get("name") or r.get("email_hash"))
                        state = "PRESENT" if has_direct_pii else "REDACTED"
                        has_pii = has_direct_pii
                    elif store == "security_service":
                        state = "PRESENT"
                        has_pii = False
                    elif store == "backup_service":
                        restore_allowed = r.get("restore_allowed", False)
                        state = "ACTIVE" if restore_allowed else "BLOCKED"
                        has_pii = bool(em or uid)
                    elif store == "integration_service":
                        enabled = r.get("enabled", False)
                        state = "ACTIVE" if enabled else "DISABLED"
                        has_pii = bool(em or uid)
                    else:
                        state = "PRESENT"
                        has_pii = True

                    obs.append(EvidenceObservation(
                        file_id=file_id,
                        captured_at=captured_at,
                        system_id=store,
                        resource_id=res_id,
                        observed_state=state,
                        user_id=uid,
                        email=em,
                        has_pii=has_pii,
                        details=r
                    ))

        elif "records" in data:
            for r in data["records"]:
                res_id = r.get("resource_id")
                if not res_id:
                    continue
                uid = r.get("customer_reference") or r.get("subject_reference") or r.get("user_id") or r.get("subject_selector")
                em = r.get("email") or r.get("owner_email") or r.get("requester_email") or r.get("customer_email")
                sys_name = r.get("system")
                if not sys_name:
                    if "customer_analytics" in full_path:
                        sys_name = "analytics_platform"
                    elif "customer_export" in full_path:
                        sys_name = "export_service"
                    elif "_" in data.get("collection", ""):
                        sys_name = data.get("collection", "").split("_")[1] + "_service"
                    else:
                        sys_name = "unknown"
                        
                if not uid and em and em.lower() in email_to_uid:
                    uid = email_to_uid[em.lower()]
                    
                has_direct_pii = bool(em or r.get("phone") or r.get("email_hash") or r.get("name"))
                if sys_name == "analytics_platform":
                    state = "PRESENT" if has_direct_pii else "ANONYMIZED"
                    has_pii = has_direct_pii
                else:
                    state = "PRESENT"
                    has_pii = has_direct_pii
                    
                obs.append(EvidenceObservation(
                    file_id=file_id,
                    captured_at=captured_at,
                    system_id=sys_name,
                    resource_id=res_id,
                    observed_state=state,
                    user_id=uid,
                    email=em,
                    has_pii=has_pii,
                    details=r
                ))
    except Exception:
        pass
    return obs


def extract_sql_observations(file_id: str, captured_at: str, full_path: str, email_to_uid: Dict[str, str]) -> List[EvidenceObservation]:
    """Extracts observations from SQLite-compatible SQL snapshot exports."""
    obs = []
    if not full_path.endswith(".sql"):
        return obs
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            con.executescript(f.read())
            
        tables = [t[0] for t in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        
        table_sys_map = {
            "customer_profiles": ("account_service", "PRESENT"),
            "customer_search_documents": ("search_service", "PRESENT"),
            "search_documents_primary": ("search_service", "PRESENT"),
            "customer_analytics_profiles": ("analytics_platform", "ANONYMIZED"),
            "support_records": ("support_platform", "REDACTED"),
            "customer_exports": ("export_service", "PRESENT"),
            "security_audit_records": ("security_service", "PRESENT")
        }
        
        for t, (sys_name, def_state) in table_sys_map.items():
            if t in tables:
                for r in con.execute(f"SELECT * FROM {t}").fetchall():
                    res_id = r["resource_id"] if "resource_id" in r.keys() else None
                    if not res_id: continue
                    uid = r["customer_reference"] if "customer_reference" in r.keys() else (r["subject_reference"] if "subject_reference" in r.keys() else None)
                    em = r["email"] if "email" in r.keys() else (r["owner_email"] if "owner_email" in r.keys() else (r["customer_email"] if "customer_email" in r.keys() else None))
                    if not uid and em and em.lower() in email_to_uid:
                        uid = email_to_uid[em.lower()]
                    
                    has_pii = bool(em or (uid and sys_name != "security_service"))
                    obs.append(EvidenceObservation(
                        file_id=file_id,
                        captured_at=captured_at,
                        system_id=sys_name,
                        resource_id=res_id,
                        observed_state=def_state if not has_pii and def_state in ("REDACTED", "ANONYMIZED") else "PRESENT",
                        user_id=uid,
                        email=em,
                        has_pii=has_pii,
                        details=dict(r)
                    ))
                    
        if "connector_subscriptions" in tables:
            for r in con.execute("SELECT * FROM connector_subscriptions").fetchall():
                res_id = r["resource_id"]
                enabled = bool(r["enabled"])
                uid = r["customer_reference"] if "customer_reference" in r.keys() else None
                em = r["customer_email"] if "customer_email" in r.keys() else None
                if not uid and em and em.lower() in email_to_uid:
                    uid = email_to_uid[em.lower()]
                obs.append(EvidenceObservation(
                    file_id=file_id,
                    captured_at=captured_at,
                    system_id="integration_service",
                    resource_id=res_id,
                    observed_state="ACTIVE" if enabled else "DISABLED",
                    user_id=uid,
                    email=em,
                    has_pii=bool(em or uid),
                    details=dict(r)
                ))
                
        if "backup_restore_entries" in tables:
            for r in con.execute("SELECT * FROM backup_restore_entries").fetchall():
                res_id = r["resource_id"]
                restore_allowed = bool(r["restore_allowed"])
                uid = r["customer_reference"] if "customer_reference" in r.keys() else None
                em = r["customer_email"] if "customer_email" in r.keys() else None
                if not uid and em and em.lower() in email_to_uid:
                    uid = email_to_uid[em.lower()]
                obs.append(EvidenceObservation(
                    file_id=file_id,
                    captured_at=captured_at,
                    system_id="backup_service",
                    resource_id=res_id,
                    observed_state="ACTIVE" if restore_allowed else "BLOCKED",
                    user_id=uid,
                    email=em,
                    has_pii=bool(em or uid),
                    details=dict(r)
                ))

        for rt in [t for t in tables if "replica" in t or t == "customer_data_primary"]:
            cols = [c[1] for c in con.execute(f"PRAGMA table_info({rt})").fetchall()]
            if "record_json" in cols:
                for r in con.execute(f"SELECT * FROM {rt}").fetchall():
                    payload = json.loads(r["record_json"])
                    res_id = r["resource_id"]
                    sys_name = r["origin_system"]
                    uid = payload.get("customer_reference") or payload.get("subject_reference") or payload.get("user_id") or payload.get("subject_selector")
                    em = payload.get("email") or payload.get("owner_email") or payload.get("requester_email") or payload.get("customer_email")
                    doc = payload.get("document", {})
                    if isinstance(doc, dict):
                        em = em or doc.get("email")
                        uid = uid or doc.get("customer_reference")
                    if not uid and em and em.lower() in email_to_uid:
                        uid = email_to_uid[em.lower()]
                    obs.append(EvidenceObservation(
                        file_id=file_id,
                        captured_at=captured_at,
                        system_id=sys_name,
                        resource_id=res_id,
                        observed_state="PRESENT",
                        user_id=uid,
                        email=em,
                        has_pii=True,
                        details={"table": rt, "payload": payload}
                    ))
            elif rt in ("customer_profiles_failover_replica", "customer_profiles_primary"):
                for r in con.execute(f"SELECT * FROM {rt}").fetchall():
                    res_id = r["resource_id"]
                    uid = r["user_id"]
                    obs.append(EvidenceObservation(
                        file_id=file_id,
                        captured_at=captured_at,
                        system_id="account_service",
                        resource_id=res_id,
                        observed_state="PRESENT",
                        user_id=uid,
                        has_pii=True,
                        details={"table": rt, "row": dict(r)}
                    ))
    except Exception:
        pass
    finally:
        con.close()
    return obs


def extract_log_observations(file_id: str, captured_at: str, full_path: str, email_to_uid: Dict[str, str], hash_to_uid: Optional[Dict[str, str]] = None) -> List[EvidenceObservation]:
    """Extracts observations from structured, syslog, and key-value logs with trace correlation."""
    obs = []
    if not full_path.endswith(".log"):
        return obs
    traces = {}
    hash_map = hash_to_uid or {}
    
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                
                m_tr = re.search(r"\b((?:tr|rb)-[a-zA-Z0-9_-]+)\b", line_str)
                tid = m_tr.group(1) if m_tr else None
                
                uids = set(re.findall(r"\b(user_\d+)\b", line_str))
                emails = set(re.findall(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", line_str))
                for em in emails:
                    if em.lower() in email_to_uid:
                        uids.add(email_to_uid[em.lower()])
                # Check SHA256 hashes
                hashes = set(re.findall(r"\b([a-f0-9]{64})\b", line_str))
                for h in hashes:
                    if h in hash_map:
                        uids.add(hash_map[h])
                        
                res_matches = re.findall(r"(?:resource_id|resource)[=:\"\s]+([a-zA-Z0-9_]+)", line_str)
                valid_res = set(r for r in res_matches if any(r.startswith(pfx) for pfx in [
                    "account_", "analytics_", "search_", "support_", "backup_",
                    "data_flow_", "export_", "audit_record_", "marketing_", "tombstone_", "object_"
                ]))
                        
                m_sys = re.search(r"(?:service|logger|system)[=:\"\s]+([a-zA-Z0-9_]+_service|[a-zA-Z0-9_]+_platform)", line_str)
                sys_name = m_sys.group(1) if m_sys else None
                
                is_404 = "404" in line_str or "rows=0" in line_str or "rows=\"0\"" in line_str or "result=miss" in line_str
                is_enabled = "enabled=true" in line_str.lower()
                is_disabled = "enabled=false" in line_str.lower()
                is_restore_allowed = "restore_allowed=true" in line_str.lower() or "restore_allowed=1" in line_str.lower() or "eligible=true" in line_str.lower() or "deletion_block=false" in line_str.lower()
                is_restore_blocked = "restore_allowed=false" in line_str.lower() or "restore_allowed=0" in line_str.lower() or "eligible=false" in line_str.lower() or "deletion_block=true" in line_str.lower()
                has_rows_1 = "rows=1" in line_str or "rows=\"1\"" in line_str

                if tid:
                    if tid not in traces:
                        traces[tid] = {"users": set(), "emails": set(), "resources": set(), "systems": set(), "lines": []}
                    traces[tid]["users"].update(uids)
                    traces[tid]["emails"].update(emails)
                    traces[tid]["resources"].update(valid_res)
                    if sys_name: traces[tid]["systems"].add(sys_name)
                    traces[tid]["lines"].append({
                        "line": line_str,
                        "is_404": is_404,
                        "is_enabled": is_enabled,
                        "is_disabled": is_disabled,
                        "is_restore_allowed": is_restore_allowed,
                        "is_restore_blocked": is_restore_blocked,
                        "has_rows_1": has_rows_1
                    })
                    
        for tid, tdata in traces.items():
            primary_uid = list(tdata["users"])[0] if tdata["users"] else None
            primary_em = list(tdata["emails"])[0] if tdata["emails"] else None
            primary_sys = list(tdata["systems"])[0] if tdata["systems"] else None
            
            for res_id in tdata["resources"]:
                sys_id = primary_sys or "unknown"
                if sys_id == "unknown":
                    for pfx, s_id in [("account_", "account_service"), ("analytics_", "analytics_platform"), ("search_", "search_service"), ("support_", "support_platform"), ("backup_", "backup_service"), ("data_flow_", "integration_service"), ("audit_record_", "security_service")]:
                        if res_id.startswith(pfx):
                            sys_id = s_id
                            break
                            
                has_404 = any(l["is_404"] for l in tdata["lines"])
                has_enabled = any(l["is_enabled"] for l in tdata["lines"])
                has_disabled = any(l["is_disabled"] for l in tdata["lines"])
                has_restore_allowed = any(l["is_restore_allowed"] for l in tdata["lines"])
                has_restore_blocked = any(l["is_restore_blocked"] for l in tdata["lines"])
                has_rows_1 = any(l["has_rows_1"] for l in tdata["lines"])
                
                if has_404:
                    state = "ABSENT"
                    has_pii = False
                elif has_enabled:
                    state = "ACTIVE"
                    has_pii = bool(primary_em or primary_uid)
                elif has_disabled:
                    state = "DISABLED"
                    has_pii = False
                elif has_restore_allowed:
                    state = "ACTIVE"
                    has_pii = bool(primary_em or primary_uid)
                elif has_restore_blocked:
                    state = "BLOCKED"
                    has_pii = False
                elif sys_id == "analytics_platform":
                    if any("email=null" in l["line"] and "customer_reference=null" in l["line"] for l in tdata["lines"]):
                        state, has_pii = "ANONYMIZED", False
                    elif has_rows_1:
                        state, has_pii = "PRESENT", True
                    else:
                        state, has_pii = "ANONYMIZED", False
                elif sys_id == "support_platform":
                    has_direct_pii = bool(primary_em)
                    state = "PRESENT" if has_direct_pii else "REDACTED"
                    has_pii = has_direct_pii
                elif sys_id == "security_service":
                    state = "PRESENT"
                    has_pii = False
                else:
                    state = "PRESENT"
                    has_pii = True
                    
                obs.append(EvidenceObservation(
                    file_id=file_id,
                    captured_at=captured_at,
                    system_id=sys_id,
                    resource_id=res_id,
                    observed_state=state,
                    user_id=primary_uid,
                    email=primary_em,
                    has_pii=has_pii,
                    details={"trace_id": tid, "line_count": len(tdata["lines"])}
                ))
    except Exception:
        pass
    return obs


class EvidenceIngestor:
    """Ingests and indexes all evidence files in dataset/evidence/."""

    def __init__(self, evidence_manifest: List[Dict[str, str]], dataset_dir: str, email_to_uid: Dict[str, str], hash_to_uid: Optional[Dict[str, str]] = None):
        self.evidence_manifest = evidence_manifest
        self.dataset_dir = dataset_dir
        self.email_to_uid = email_to_uid
        self.hash_to_uid = hash_to_uid or {}
        self.observations: List[EvidenceObservation] = []
        self._ingest_all()

    def _ingest_all(self):
        for f_info in self.evidence_manifest:
            file_id = f_info["file_id"]
            file_path = f_info["file_path"]
            captured_at = f_info["captured_at"]
            full_path = os.path.join(self.dataset_dir, file_path)
            
            if not os.path.exists(full_path):
                continue
                
            if file_path.endswith(".json"):
                self.observations.extend(extract_json_observations(file_id, captured_at, full_path, self.email_to_uid))
            elif file_path.endswith(".sql"):
                self.observations.extend(extract_sql_observations(file_id, captured_at, full_path, self.email_to_uid))
            elif file_path.endswith(".log"):
                self.observations.extend(extract_log_observations(file_id, captured_at, full_path, self.email_to_uid, self.hash_to_uid))
            elif file_path.endswith(".txt"):
                self.observations.extend(extract_txt_observations(file_id, captured_at, full_path, self.email_to_uid))
            elif file_path.endswith(".pdf"):
                self.observations.extend(extract_pdf_observations(file_id, captured_at, full_path, self.email_to_uid))
