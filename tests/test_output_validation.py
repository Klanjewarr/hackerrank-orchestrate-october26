"""Tests for output validation against the 20-point checklist.
"""

import unittest
import os
import csv
import json
from src.validate_output import validate_output_file


class TestOutputValidation(unittest.TestCase):

    def setUp(self):
        self.test_csv = "tests/temp_test_output.csv"

    def tearDown(self):
        if os.path.exists(self.test_csv):
            os.remove(self.test_csv)

    def test_valid_output(self):
        with open(self.test_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["case_id", "deletion_status", "steps_json"])
            writer.writerow(["case_01", "COMPLETE", json.dumps([
                {"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_001", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "ev_01"}
            ])])
            writer.writerow(["case_02", "NOT_APPLICABLE", "[]"])
            writer.writerow(["case_03", "INCOMPLETE", json.dumps([
                {"step_no": 1, "phase": "FINDING", "system_id": "account_service", "resource_id": "account_003", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "ev_02"},
                {"step_no": 2, "phase": "REMEDIATION", "system_id": "account_service", "resource_id": "account_003", "operation": "DELETE_RECORD", "state": "ABSENT", "evidence_id": ""},
                {"step_no": 3, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_003", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": ""}
            ])])

        is_valid, errors = validate_output_file(self.test_csv, expected_case_count=3)
        self.assertTrue(is_valid, f"Validation failed with: {errors}")

    def test_corrupt_header(self):
        with open(self.test_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["case_id", "status", "steps"]) # Wrong headers
            writer.writerow(["case_01", "NOT_APPLICABLE", "[]"])

        is_valid, errors = validate_output_file(self.test_csv, expected_case_count=1)
        self.assertFalse(is_valid)
        self.assertTrue(any("Header mismatch" in e for e in errors))

    def test_complete_with_finding_fails(self):
        with open(self.test_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["case_id", "deletion_status", "steps_json"])
            writer.writerow(["case_01", "COMPLETE", json.dumps([
                {"step_no": 1, "phase": "FINDING", "system_id": "account_service", "resource_id": "account_001", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "ev_01"}
            ])])

        is_valid, errors = validate_output_file(self.test_csv, expected_case_count=1)
        self.assertFalse(is_valid)
        self.assertTrue(any("non-VERIFICATION step" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
