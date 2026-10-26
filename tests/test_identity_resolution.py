"""Tests for identity resolution and request authorization.
"""

import unittest
from src.identity_resolution import IdentityResolver, is_deletion_request


class TestIdentityResolution(unittest.TestCase):

    def setUp(self):
        self.identities = [
            {"user_id": "user_01", "name": "Alice Smith", "email": "alice@example.com", "phone": "+1234567890", "email_hash": "hash_alice_1", "updated_at": "2026-01-01T00:00:00Z"},
            {"user_id": "user_02", "name": "Bob Jones", "email": "bob@example.com", "phone": "+1987654321", "email_hash": "hash_bob_1", "updated_at": "2026-01-01T00:00:00Z"}
        ]
        self.audit_log = [
            {"audit_id": "audit_1", "user_id": "user_01", "event_time": "2025-06-01T00:00:00Z", "field_name": "email", "old_value": "alice.old@example.com", "new_value": "alice@example.com"},
            {"audit_id": "audit_2", "user_id": "user_01", "event_time": "2025-06-01T00:00:00Z", "field_name": "email_hash", "old_value": "hash_alice_old", "new_value": "hash_alice_1"}
        ]
        self.system_activity = [
            {"activity_id": "act_1", "event_time": "2026-02-01T00:00:00Z", "event_type": "LINK_RESOURCE_IDENTITY", "details": "Linked resource_01 to alice.alias@example.com and user_01", "resource_id": "resource_01"}
        ]
        self.resolver = IdentityResolver(self.identities, self.audit_log, self.system_activity)

    def test_current_email_resolution(self):
        self.assertEqual(self.resolver.resolve_user_id("alice@example.com"), "user_01")
        self.assertEqual(self.resolver.resolve_user_id("bob@example.com"), "user_02")

    def test_historical_email_resolution(self):
        self.assertEqual(self.resolver.resolve_user_id("alice.old@example.com"), "user_01")

    def test_hash_resolution(self):
        self.assertEqual(self.resolver.resolve_user_id("hash_alice_1"), "user_01")
        self.assertEqual(self.resolver.resolve_user_id("hash_alice_old"), "user_01")

    def test_activity_link_resolution(self):
        self.assertEqual(self.resolver.resolve_user_id("alice.alias@example.com"), "user_01")
        self.assertEqual(self.resolver.resolve_user_id("resource_01"), "user_01")

    def test_unknown_identifier(self):
        self.assertIsNone(self.resolver.resolve_user_id("unknown@example.com"))

    def test_deletion_request_authorization(self):
        self.assertTrue(is_deletion_request("Please delete my account permanently."))
        self.assertTrue(is_deletion_request("Je demande la suppression définitive de mes données."))
        self.assertTrue(is_deletion_request("Bitte mein Konto löschen."))
        self.assertTrue(is_deletion_request("Por favor elimine mi cuenta."))

    def test_non_deletion_request_authorization(self):
        self.assertFalse(is_deletion_request("The mobile number on my profile is out of date. Please replace it with the new one and leave the account active."))
        self.assertFalse(is_deletion_request("Please stop the promotional emails. I still need the account and my order history, so I am not asking for deletion."))
        self.assertFalse(is_deletion_request("I'd like to download my account information in a portable format. Please keep the account as it is."))
        self.assertFalse(is_deletion_request("I can't access my profile and need help resetting the login. Do not close the account."))
        self.assertFalse(is_deletion_request("My surname is misspelled on the account. Can you correct it without removing any of my records?"))


if __name__ == "__main__":
    unittest.main()
