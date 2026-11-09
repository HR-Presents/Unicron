"""Provenance-based jurisdiction regression tests."""
import unittest

from backend.app.evidence import is_uae_jurisdiction


class EvidenceJurisdictionTests(unittest.TestCase):
    def test_eu_is_not_uae(self):
        self.assertFalse(is_uae_jurisdiction("EU"))

    def test_european_union_is_not_uae(self):
        self.assertFalse(
            is_uae_jurisdiction("European Union")
        )

    def test_uae_is_recognized(self):
        self.assertTrue(is_uae_jurisdiction("UAE"))

    def test_full_uae_name_is_recognized(self):
        self.assertTrue(
            is_uae_jurisdiction("United Arab Emirates")
        )

    def test_unknown_jurisdiction_fails_closed(self):
        self.assertFalse(is_uae_jurisdiction(None))


if __name__ == "__main__":
    unittest.main()
