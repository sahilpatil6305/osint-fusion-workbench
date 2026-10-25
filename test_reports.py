"""Offline tests for report generation and analysis normalization."""
import json
import unittest

from reports import json_bytes, markdown_report, normalize_analysis, pdf_report


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.analysis = normalize_analysis({
            "executive_summary": "Synthetic incident with special characters: <script>&.",
            "entities": {"people": [{"name": "Analyst A", "role": "reporter"}]},
            "timeline": [{"time": "2026-10-24", "event": "Service disruption", "source_excerpt": "Systems unavailable."}],
            "relationships": [{"entity_a": "Org A", "relation": "reported", "entity_b": "outage"}],
            "key_claims": [{"claim": "An outage occurred", "type": "allegation", "excerpt": "Systems unavailable."}],
            "investigative_leads": [{"lead": "Review logs", "rationale": "Could add context"}],
            "unanswered_questions": ["When was service restored?"],
            "uncertainty_warnings": ["No independent verification."],
            "analyst_note": "Synthetic data only.",
            "extension": {"preserve": True},
        })

    def test_json_round_trip_preserves_extra_fields(self):
        encoded = json_bytes(self.analysis)
        self.assertEqual(json.loads(encoded), self.analysis)
        self.assertIn(b'"extension"', encoded)

    def test_markdown_sections_and_unverified_leads(self):
        report = markdown_report(self.analysis)
        for text in ("## Executive Summary", "## Entity Inventory", "## Event Timeline",
                     "## Relationships", "## Claims & Supporting Evidence",
                     "UNVERIFIED — REQUIRES HUMAN REVIEW", "## Methodology & Limitations"):
            self.assertIn(text, report)

    def test_pdf_is_valid_nonempty_and_handles_empty_sections(self):
        content = pdf_report(self.analysis)
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertGreater(len(content), 1000)
        self.assertTrue(pdf_report(normalize_analysis({"executive_summary": "short"})).startswith(b"%PDF-"))

    def test_normalization_handles_missing_fields_and_preserves_extensions(self):
        result = normalize_analysis({"entities": None, "timeline": "malformed", "extension": 7})
        self.assertEqual(result["entities"]["people"], [])
        self.assertEqual(result["timeline"], [])
        self.assertEqual(result["extension"], 7)


if __name__ == "__main__":
    unittest.main()
