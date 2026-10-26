"""Tests for step ordering, operation priority, and 1-based sequential renumbering.
"""

import unittest
from src.step_ordering import sort_and_renumber_steps, PHASE_ORDER, OPERATION_ORDER


class TestStepOrdering(unittest.TestCase):

    def test_phase_ordering(self):
        # Steps out of order: VERIFICATION, FINDING, REMEDIATION
        raw_steps = [
            {"step_no": 99, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_001", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": ""},
            {"step_no": 5, "phase": "FINDING", "system_id": "search_service", "resource_id": "search_001", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "ev_01"},
            {"step_no": 12, "phase": "REMEDIATION", "system_id": "search_service", "resource_id": "search_001", "operation": "DELETE_RECORD", "state": "ABSENT", "evidence_id": ""}
        ]
        sorted_steps = sort_and_renumber_steps(raw_steps)
        
        self.assertEqual(len(sorted_steps), 3)
        self.assertEqual(sorted_steps[0]["step_no"], 1)
        self.assertEqual(sorted_steps[0]["phase"], "FINDING")
        self.assertEqual(sorted_steps[1]["step_no"], 2)
        self.assertEqual(sorted_steps[1]["phase"], "REMEDIATION")
        self.assertEqual(sorted_steps[2]["step_no"], 3)
        self.assertEqual(sorted_steps[2]["phase"], "VERIFICATION")

    def test_remediation_operation_precedence(self):
        # In remediation, data flow must be disabled and restore blocked BEFORE deleting records
        raw_steps = [
            {"phase": "REMEDIATION", "system_id": "account_service", "resource_id": "account_001", "operation": "DELETE_RECORD", "state": "ABSENT"},
            {"phase": "REMEDIATION", "system_id": "integration_service", "resource_id": "data_flow_01", "operation": "DISABLE_DATA_FLOW", "state": "DISABLED"},
            {"phase": "REMEDIATION", "system_id": "backup_service", "resource_id": "backup_01", "operation": "BLOCK_RESTORE", "state": "BLOCKED"}
        ]
        sorted_steps = sort_and_renumber_steps(raw_steps)
        self.assertEqual(sorted_steps[0]["operation"], "DISABLE_DATA_FLOW")
        self.assertEqual(sorted_steps[1]["operation"], "BLOCK_RESTORE")
        self.assertEqual(sorted_steps[2]["operation"], "DELETE_RECORD")

    def test_lexicographical_tie_breaking(self):
        # Same operation, different system_id / resource_id
        raw_steps = [
            {"phase": "VERIFICATION", "system_id": "support_platform", "resource_id": "support_002", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT"},
            {"phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_001", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT"},
            {"phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_002", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT"}
        ]
        sorted_steps = sort_and_renumber_steps(raw_steps)
        self.assertEqual(sorted_steps[0]["resource_id"], "account_001")
        self.assertEqual(sorted_steps[1]["resource_id"], "account_002")
        self.assertEqual(sorted_steps[2]["resource_id"], "support_002")


if __name__ == "__main__":
    unittest.main()
