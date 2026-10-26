"""Main entry point for the Ghost Data Still Exists deletion audit agent.
"""

import sys
import os
import argparse
import time

# Ensure repository root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.data_loader import load_dataset
from src.identity_resolution import IdentityResolver
from src.evidence_ingestion import EvidenceIngestor
from src.evidence_retrieval import ResourceGraph
from src.temporal_state import ResourceTemporalEvaluator
from src.deletion_audit import DeletionAuditEngine
from src.output_generator import write_output_csv
from src.validate_output import validate_output_file


def run_pipeline(dataset_dir: str = "dataset", output_path: str = "output.csv", eval_samples: bool = False):
    print("=" * 70)
    print("Ghost Data Still Exists: AI Deletion Audit Agent")
    print(f"Dataset directory : {dataset_dir}")
    print(f"Output path       : {output_path}")
    print("=" * 70)

    start_time = time.time()
    
    # 1. Load datasets
    print("\n[1/5] Loading datasets...")
    data = load_dataset(dataset_dir)
    user_identities = data.get("user_identities", [])
    user_audit_log = data.get("user_audit_log", [])
    system_activity = data.get("system_activity", [])
    evidence_manifest = data.get("evidence_files", [])
    
    expected_outputs = {}
    if eval_samples:
        requests = data.get("sample_deletion_requests", [])
        expected_outputs = {r["case_id"]: r for r in data.get("sample_output", [])}
        print(f"  Loaded {len(requests)} sample requests for evaluation.")
    else:
        requests = data.get("deletion_requests", [])
        print(f"  Loaded {len(requests)} evaluation requests.")

    # 2. Initialize identity resolution
    print("\n[2/5] Initializing identity resolution...")
    resolver = IdentityResolver(user_identities, user_audit_log, system_activity)
    print(f"  Mapped {len(resolver.uid_to_profile)} users, {len(resolver.email_to_uid)} emails, {len(resolver.phone_to_uid)} phones, {len(resolver.hash_to_uid)} hashes.")

    # 3. Ingest evidence files
    print("\n[3/5] Ingesting evidence files...")
    ingestor = EvidenceIngestor(evidence_manifest, dataset_dir, resolver.email_to_uid, resolver.hash_to_uid)
    print(f"  Extracted {len(ingestor.observations)} observations across {len(evidence_manifest)} evidence files.")

    # 4. Build resource graph and temporal evaluator
    print("\n[4/5] Building resource graph and temporal engine...")
    graph = ResourceGraph(resolver, ingestor.observations, system_activity)
    evaluator = ResourceTemporalEvaluator(ingestor.observations, evidence_manifest)
    engine = DeletionAuditEngine(resolver, graph, evaluator)
    print(f"  Indexed resources for {len(graph.user_to_resources)} users.")

    # 5. Audit all requests
    print(f"\n[5/5] Auditing {len(requests)} requests...")
    results = []
    status_counts = {"COMPLETE": 0, "INCOMPLETE": 0, "NOT_APPLICABLE": 0}

    for idx, req in enumerate(requests, 1):
        cid, status, steps = engine.audit_request(req)
        results.append((cid, status, steps))
        status_counts[status] = status_counts.get(status, 0) + 1
        
        if idx % 50 == 0 or idx == len(requests):
            print(f"  Processed {idx}/{len(requests)} cases (current counts: {status_counts})...")

    # Write output
    print(f"\nWriting output to {output_path}...")
    write_output_csv(results, output_path)
    
    elapsed = time.time() - start_time
    print(f"Run completed in {elapsed:.2f} seconds.")
    print(f"Summary: {status_counts}")

    # Validate output
    expected_rows = len(requests)
    print(f"\nValidating output against 20-point compliance checklist ({expected_rows} rows)...")
    is_valid, errors = validate_output_file(output_path, expected_case_count=expected_rows)
    if is_valid:
        print("  [PASSED] All 20 validation checks passed successfully!")
    else:
        print(f"  [FAILED] Found {len(errors)} errors:")
        for err in errors[:10]:
            print(f"    * {err}")

    # Evaluate against samples if requested
    if eval_samples and expected_outputs:
        print("\nEvaluating against sample ground truth...")
        correct_status = 0
        total_samples = len(requests)
        for cid, status, steps in results:
            exp_status = expected_outputs[cid]["deletion_status"]
            if status == exp_status:
                correct_status += 1
            else:
                print(f"  [MISMATCH] {cid}: predicted={status}, expected={exp_status}")
        accuracy = (correct_status / total_samples) * 100
        print(f"Sample Status Accuracy: {correct_status}/{total_samples} ({accuracy:.1f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghost Data Still Exists Deletion Audit Agent")
    parser.add_argument("--dataset_dir", default="dataset", help="Path to dataset directory")
    parser.add_argument("--output_path", default="output.csv", help="Path for output.csv")
    parser.add_argument("--evaluate_samples", action="store_true", help="Evaluate against sample dataset")
    args = parser.parse_args()

    run_pipeline(args.dataset_dir, args.output_path, args.evaluate_samples)
