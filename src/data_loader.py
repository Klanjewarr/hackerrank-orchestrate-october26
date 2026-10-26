"""Data loader module for Ghost Data Still Exists.
Loads and validates input datasets from CSV files.
"""

import os
import csv
from typing import Dict, List, Any


def load_csv(file_path: str) -> List[Dict[str, str]]:
    """Loads a CSV file into a list of row dictionaries."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def load_dataset(dataset_dir: str = "dataset") -> Dict[str, Any]:
    """Loads all primary participant dataset files."""
    data = {}
    
    del_req_path = os.path.join(dataset_dir, "deletion_requests.csv")
    if os.path.exists(del_req_path):
        data["deletion_requests"] = load_csv(del_req_path)
        
    sample_req_path = os.path.join(dataset_dir, "sample_deletion_requests.csv")
    if os.path.exists(sample_req_path):
        data["sample_deletion_requests"] = load_csv(sample_req_path)
        
    sample_out_path = os.path.join(dataset_dir, "sample_output.csv")
    if os.path.exists(sample_out_path):
        data["sample_output"] = load_csv(sample_out_path)
        
    identities_path = os.path.join(dataset_dir, "user_identities.csv")
    if os.path.exists(identities_path):
        data["user_identities"] = load_csv(identities_path)
        
    audit_log_path = os.path.join(dataset_dir, "user_audit_log.csv")
    if os.path.exists(audit_log_path):
        data["user_audit_log"] = load_csv(audit_log_path)
        
    rules_path = os.path.join(dataset_dir, "deletion_rules.csv")
    if os.path.exists(rules_path):
        data["deletion_rules"] = load_csv(rules_path)
        
    ev_files_path = os.path.join(dataset_dir, "evidence_files.csv")
    if os.path.exists(ev_files_path):
        data["evidence_files"] = load_csv(ev_files_path)
        
    activity_path = os.path.join(dataset_dir, "system_activity.csv")
    if os.path.exists(activity_path):
        data["system_activity"] = load_csv(activity_path)
        
    return data
