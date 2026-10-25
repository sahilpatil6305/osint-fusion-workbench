"""Synthetic offline tests for source upload extraction and attribution."""
import json
from io import BytesIO
import unittest

from reports import json_bytes, markdown_report, pdf_report
from source_documents import (MAX_FILE_BYTES, MAX_TOTAL_TEXT_CHARS, combine_sources,
                              extract_document, validate_attributions)


class SourceDocumentTests(unittest.TestCase):
    @staticmethod
    def make_pdf(text="Synthetic report text"):
        from reportlab.pdfgen import canvas
        data = BytesIO()
        pdf = canvas.Canvas(data)
        pdf.drawString(72, 720, text)
        pdf.save()
        return data.getvalue()

    def test_txt_and_markdown_utf8(self):
        txt, warnings = extract_document("brief.txt", "Incident café".encode(), "SRC-01")
        md, md_warnings = extract_document("brief.md", b"# Incident\nDetails", "SRC-02")
        self.assertEqual(txt.text, "Incident café")
        self.assertEqual(md.text, "# Incident\nDetails")
        self.assertFalse(warnings + md_warnings)

    def test_invalid_utf8_is_replaced_and_warned(self):
        source, warnings = extract_document("odd.txt", b"valid\xfftext")
        self.assertIn("\ufffd", source.text)
        self.assertTrue(any("invalid UTF-8" in warning for warning in warnings))

    def test_normal_pdf_has_page_markers_and_count(self):
        source, warnings = extract_document("report.pdf", self.make_pdf())
        self.assertEqual(source.page_count, 1)
        self.assertIn("[Page 1]", source.text)
        self.assertIn("Synthetic report text", source.text)
        self.assertFalse(warnings)

    def test_empty_unreadable_and_unsupported_files_are_rejected(self):
        for filename, content in (("empty.txt", b""), ("blank.md", b" \n"), ("broken.pdf", b"not a PDF"), ("unknown.docx", b"text")):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                extract_document(filename, content)

    def test_scanned_pdf_is_not_silently_accepted(self):
        from reportlab.pdfgen import canvas
        data = BytesIO()
        pdf = canvas.Canvas(data)
        pdf.showPage()
        pdf.save()
        pdf_data = data.getvalue()
        with self.assertRaisesRegex(ValueError, "no selectable text"):
            extract_document("scan.pdf", pdf_data)

    def test_encrypted_pdf_is_reported(self):
        from reportlab.pdfgen import canvas
        data = BytesIO()
        pdf = canvas.Canvas(data, encrypt="synthetic-password")
        pdf.drawString(72, 720, "Encrypted synthetic report")
        pdf.save()
        with self.assertRaisesRegex(ValueError, "encrypted"):
            extract_document("locked.pdf", data.getvalue())

    def test_per_file_and_combined_text_limits(self):
        with self.assertRaisesRegex(ValueError, "10 MB"):
            extract_document("large.txt", b"x" * (MAX_FILE_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "No text was truncated"):
            combine_sources([], "x" * (MAX_TOTAL_TEXT_CHARS + 1))

    def test_multiple_uploads_and_pasted_source_ids(self):
        sources = [extract_document("one.txt", b"One", "SRC-01")[0],
                   extract_document("two.md", b"Two", "SRC-02")[0]]
        combined, all_sources = combine_sources(sources, "Pasted content")
        self.assertEqual([source.source_id for source in all_sources], ["PASTED-01", "SRC-01", "SRC-02"])
        self.assertIn("FILENAME: one.txt", combined)
        self.assertIn("FILENAME: two.md", combined)

    def test_source_attribution_survives_all_exports(self):
        report = {
            "executive_summary": "Synthetic.",
            "sources": [{"source_id": "SRC-01", "filename": "brief.pdf", "characters": 18}],
            "extraction_warnings": ["One page had no text."],
            "key_claims": [{"claim": "A service was disrupted", "type": "allegation", "source_id": "SRC-01", "page": 2}],
        }
        encoded = json_bytes(report)
        self.assertEqual(json.loads(encoded), report)
        markdown = markdown_report(report)
        self.assertIn("brief.pdf", markdown)
        self.assertIn("SRC-01", markdown)
        self.assertIn("Page: 2", markdown)
        self.assertIn("One page had no text", markdown)
        self.assertTrue(pdf_report(report).startswith(b"%PDF-"))

    def test_attribution_validation_removes_fabricated_source_page_and_excerpt(self):
        source, _ = extract_document("brief.pdf", self.make_pdf("Confirmed source wording"), "SRC-01")
        analysis = {
            "entities": {"people": [], "organizations": [], "locations": [], "dates": [], "technologies": []},
            "key_claims": [
                {"claim": "Supported", "source_id": "SRC-01", "page": 1, "excerpt": "Confirmed source wording"},
                {"claim": "Unsupported", "source_id": "SRC-99", "page": 99, "excerpt": "Fabricated quotation"},
            ],
        }
        warnings = validate_attributions(analysis, [source])
        supported, unsupported = analysis["key_claims"]
        self.assertEqual(supported["source_filenames"], ["brief.pdf"])
        self.assertEqual(supported["page"], 1)
        self.assertNotIn("source_id", unsupported)
        self.assertNotIn("page", unsupported)
        self.assertNotIn("excerpt", unsupported)
        self.assertGreaterEqual(len(warnings), 3)


if __name__ == "__main__":
    unittest.main()
