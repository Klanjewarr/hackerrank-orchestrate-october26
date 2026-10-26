"""Tests for policy engine rules, system mapping, and allowed operations.
"""

import unittest
from src.policy_engine import infer_system_id, get_required_action, get_operation_for_action


class TestPolicyEngine(unittest.TestCase):

    def test_infer_system_id(self):
        self.assertEqual(infer_system_id("account_001"), "account_service")
        self.assertEqual(infer_system_id("search_123"), "search_service")
        self.assertEqual(infer_system_id("support_99"), "support_platform")
        self.assertEqual(infer_system_id("analytics_55"), "analytics_platform")
        self.assertEqual(infer_system_id("backup_42"), "backup_service")
        self.assertEqual(infer_system_id("data_flow_07"), "integration_service")
        self.assertEqual(infer_system_id("audit_record_99"), "security_service")
        self.assertEqual(infer_system_id("tombstone_10"), "identity_service")
        self.assertEqual(infer_system_id("export_50"), "export_service")

    def test_get_required_action(self):
        self.assertEqual(get_required_action("account_service"), "DELETE")
        self.assertEqual(get_required_action("search_service"), "DELETE")
        self.assertEqual(get_required_action("export_service"), "DELETE")
        self.assertEqual(get_required_action("support_platform"), "REDACT")
        self.assertEqual(get_required_action("identity_service"), "REDACT")
        self.assertEqual(get_required_action("analytics_platform"), "ANONYMIZE")
        self.assertEqual(get_required_action("security_service"), "RETAIN")
        self.assertEqual(get_required_action("backup_service"), "BLOCK")
        self.assertEqual(get_required_action("integration_service"), "DISABLE")

    def test_finding_operations(self):
        self.assertEqual(get_operation_for_action("DELETE", "FINDING"), ("REPORT_REMAINING_RECORD", "PRESENT"))
        self.assertEqual(get_operation_for_action("REDACT", "FINDING"), ("REPORT_EXPOSED_PII", "PRESENT"))
        self.assertEqual(get_operation_for_action("ANONYMIZE", "FINDING"), ("REPORT_EXPOSED_PII", "PRESENT"))
        self.assertEqual(get_operation_for_action("DISABLE", "FINDING"), ("REPORT_ACTIVE_DATA_FLOW", "ACTIVE"))
        self.assertEqual(get_operation_for_action("BLOCK", "FINDING"), ("REPORT_RESTORE_RISK", "ACTIVE"))

    def test_remediation_operations(self):
        self.assertEqual(get_operation_for_action("DISABLE", "REMEDIATION"), ("DISABLE_DATA_FLOW", "DISABLED"))
        self.assertEqual(get_operation_for_action("BLOCK", "REMEDIATION"), ("BLOCK_RESTORE", "BLOCKED"))
        self.assertEqual(get_operation_for_action("DELETE", "REMEDIATION"), ("DELETE_RECORD", "ABSENT"))
        self.assertEqual(get_operation_for_action("REDACT", "REMEDIATION"), ("REDACT_RECORD", "REDACTED"))
        self.assertEqual(get_operation_for_action("ANONYMIZE", "REMEDIATION"), ("ANONYMIZE_RECORD", "ANONYMIZED"))

    def test_verification_operations(self):
        self.assertEqual(get_operation_for_action("DELETE", "VERIFICATION"), ("VERIFY_RECORD_ABSENT", "ABSENT"))
        self.assertEqual(get_operation_for_action("RETAIN", "VERIFICATION"), ("VERIFY_RECORD_PRESENT", "PRESENT"))
        self.assertEqual(get_operation_for_action("REDACT", "VERIFICATION"), ("VERIFY_RECORD_REDACTED", "REDACTED"))
        self.assertEqual(get_operation_for_action("ANONYMIZE", "VERIFICATION"), ("VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"))
        self.assertEqual(get_operation_for_action("DISABLE", "VERIFICATION"), ("VERIFY_DATA_FLOW_DISABLED", "DISABLED"))
        self.assertEqual(get_operation_for_action("BLOCK", "VERIFICATION"), ("VERIFY_RESTORE_BLOCKED", "BLOCKED"))


if __name__ == "__main__":
    unittest.main()
