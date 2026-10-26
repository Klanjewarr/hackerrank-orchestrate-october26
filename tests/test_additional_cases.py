"""Additional evaluation cases created by the participant.
Implements 3 rich audit scenarios:
1. Recreation via active integration sync pipeline
2. Prohibited direct identifiers exposed on an account tombstone
3. Active backup restore path with restorable personal data
"""

import unittest
from src.identity_resolution import IdentityResolver
from src.evidence_ingestion import EvidenceObservation
from src.temporal_state import ResourceTemporalEvaluator
from src.remediation_planner import plan_remediation_and_verification


class TestAdditionalEvaluationCases(unittest.TestCase):

    def test_case_recreation_via_active_sync(self):
        """Scenario 1: Active synchronization pipeline that recreates deleted data."""
        # Setup observations
        obs = [
            EvidenceObservation(
                file_id="evidence_cust_01",
                captured_at="2026-09-01T10:00:00Z",
                system_id="account_service",
                resource_id="account_cust_101",
                observed_state="ABSENT",
                user_id="user_cust_101"
            ),
            EvidenceObservation(
                file_id="evidence_cust_02",
                captured_at="2026-09-01T11:00:00Z",
                system_id="integration_service",
                resource_id="data_flow_cust_101",
                observed_state="ACTIVE",
                user_id="user_cust_101",
                has_pii=True
            )
        ]
        
        evaluator = ResourceTemporalEvaluator(obs)
        audit_at = "2026-09-01T12:00:00Z"
        
        ev_account = evaluator.evaluate_resource_at_time("account_service", "account_cust_101", audit_at)
        ev_flow = evaluator.evaluate_resource_at_time("integration_service", "data_flow_cust_101", audit_at)
        
        evaluations = [ev_account, ev_flow]
        has_violations = any(not ev["is_compliant"] for ev in evaluations)
        self.assertTrue(has_violations)
        
        steps = plan_remediation_and_verification("case_cust_01", evaluations, is_complete=False)
        
        # Verify findings
        finding = [s for s in steps if s["phase"] == "FINDING"][0]
        self.assertEqual(finding["operation"], "REPORT_ACTIVE_DATA_FLOW")
        self.assertEqual(finding["resource_id"], "data_flow_cust_101")
        self.assertEqual(finding["evidence_id"], "evidence_cust_02")
        
        # Verify remediation precedence (DISABLE_DATA_FLOW must come first)
        remediations = [s for s in steps if s["phase"] == "REMEDIATION"]
        self.assertEqual(remediations[0]["operation"], "DISABLE_DATA_FLOW")
        self.assertEqual(remediations[0]["evidence_id"], "")

    def test_case_unredacted_tombstone(self):
        """Scenario 2: Account tombstone retains prohibited direct identifiers (email/phone)."""
        obs = [
            EvidenceObservation(
                file_id="evidence_cust_03",
                captured_at="2026-09-02T10:00:00Z",
                system_id="identity_service",
                resource_id="tombstone_cust_202",
                observed_state="PRESENT",
                user_id="user_cust_202",
                email="user202@example.com",
                has_pii=True # Direct email still exposed!
            )
        ]
        
        evaluator = ResourceTemporalEvaluator(obs)
        audit_at = "2026-09-02T12:00:00Z"
        
        ev_tombstone = evaluator.evaluate_resource_at_time("identity_service", "tombstone_cust_202", audit_at)
        self.assertFalse(ev_tombstone["is_compliant"])
        self.assertEqual(ev_tombstone["violation_type"], "EXPOSED_PII")
        
        steps = plan_remediation_and_verification("case_cust_02", [ev_tombstone], is_complete=False)
        
        finding = [s for s in steps if s["phase"] == "FINDING"][0]
        self.assertEqual(finding["operation"], "REPORT_EXPOSED_PII")
        self.assertEqual(finding["evidence_id"], "evidence_cust_03")
        
        remediation = [s for s in steps if s["phase"] == "REMEDIATION"][0]
        self.assertEqual(remediation["operation"], "REDACT_RECORD")
        self.assertEqual(remediation["state"], "REDACTED")

    def test_case_active_backup_restore_risk(self):
        """Scenario 3: Backup archive remains restorable despite workflow claim."""
        obs = [
            EvidenceObservation(
                file_id="evidence_cust_04",
                captured_at="2026-09-03T10:00:00Z",
                system_id="backup_service",
                resource_id="backup_cust_303",
                observed_state="ACTIVE", # restore allowed!
                user_id="user_cust_303"
            )
        ]
        
        evaluator = ResourceTemporalEvaluator(obs)
        audit_at = "2026-09-03T12:00:00Z"
        
        ev_backup = evaluator.evaluate_resource_at_time("backup_service", "backup_cust_303", audit_at)
        self.assertFalse(ev_backup["is_compliant"])
        self.assertEqual(ev_backup["violation_type"], "RESTORE_RISK")
        
        steps = plan_remediation_and_verification("case_cust_03", [ev_backup], is_complete=False)
        
        finding = [s for s in steps if s["phase"] == "FINDING"][0]
        self.assertEqual(finding["operation"], "REPORT_RESTORE_RISK")
        self.assertEqual(finding["state"], "ACTIVE")
        self.assertEqual(finding["evidence_id"], "evidence_cust_04")
        
        remediation = [s for s in steps if s["phase"] == "REMEDIATION"][0]
        self.assertEqual(remediation["operation"], "BLOCK_RESTORE")
        self.assertEqual(remediation["state"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
