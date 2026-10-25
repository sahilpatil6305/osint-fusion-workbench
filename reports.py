"""Validated analysis normalization and in-memory report exports."""
from datetime import datetime
import io
import json
from xml.sax.saxutils import escape as xml_escape


ENTITY_CATEGORIES = ("people", "organizations", "locations", "dates", "technologies")
LIST_FIELDS = ("timeline", "relationships", "key_claims", "investigative_leads",
               "unanswered_questions", "uncertainty_warnings")


def normalize_analysis(value):
    """Return a predictable, JSON-safe shape while preserving extra fields."""
    if not isinstance(value, dict):
        raise ValueError("The analysis response must be a JSON object.")
    result = dict(value)
    entities = result.get("entities")
    if not isinstance(entities, dict):
        entities = {}
    result["entities"] = dict(entities)
    for category in ENTITY_CATEGORIES:
        items = result["entities"].get(category, [])
        result["entities"][category] = items if isinstance(items, list) else []
    for field in LIST_FIELDS:
        items = result.get(field, [])
        result[field] = items if isinstance(items, list) else []
    for field in ("executive_summary", "analyst_note"):
        if not isinstance(result.get(field), str):
            result[field] = ""
    return result


def _text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _source_note(value):
    if not isinstance(value, dict):
        return ""
    source_ids = value.get("source_ids") or ([value["source_id"]] if value.get("source_id") else [])
    parts = []
    if source_ids:
        parts.append("Sources: " + ", ".join(map(str, source_ids)))
    filenames = value.get("source_filenames") or []
    if filenames:
        parts.append("Files: " + ", ".join(map(str, filenames)))
    if value.get("page") is not None:
        parts.append("Page: " + str(value["page"]))
    return " · ".join(parts)


def json_bytes(analysis):
    return json.dumps(analysis, ensure_ascii=False, indent=2).encode("utf-8")


def markdown_report(analysis, generated_at=None):
    stamp = generated_at or datetime.now().astimezone()
    lines = ["# OSINT Fusion Workbench — Intelligence Dossier", "",
             f"Generated: {stamp:%Y-%m-%d %H:%M:%S %Z}", "",
             "> AI-generated analysis of user-supplied text. Underlying claims have not been independently verified.",
             "", "## Source Inventory", ""]
    sources = analysis.get("sources", [])
    if sources:
        for source in sources:
            lines.append(f"- **{_text(source.get('source_id', ''))}** — {_text(source.get('filename', 'Unknown filename'))} ({_text(source.get('characters', ''))} characters)")
    else:
        lines.append("- No source inventory supplied.")
    lines.append("")
    lines.extend(["## Extraction Warnings", ""])
    warnings = analysis.get("extraction_warnings", [])
    lines.extend([f"- {_text(warning)}" for warning in warnings] or ["- None."])
    lines.extend(["", "## Executive Summary", "", _text(analysis.get("executive_summary")) or "No summary provided.", "", "## Entity Inventory", ""])
    entities = analysis.get("entities", {})
    for cat in ENTITY_CATEGORIES:
        lines += [f"### {cat.replace('_', ' ').title()}", ""]
        items = entities.get(cat, [])
        lines.extend([f"- {_text(x)}" + (f" ({_source_note(x)})" if _source_note(x) else "") for x in items] or ["- None reported."])
        lines.append("")
    sections = (("Event Timeline", "timeline"), ("Relationships", "relationships"), ("Claims & Supporting Evidence", "key_claims"), ("Investigative Leads", "investigative_leads"), ("Unanswered Questions", "unanswered_questions"), ("Uncertainty Warnings", "uncertainty_warnings"))
    for title, field in sections:
        lines += [f"## {title}", ""]
        items = analysis.get(field, [])
        if not items:
            lines += ["None reported.", ""]
            continue
        for item in items:
            if field == "investigative_leads" and isinstance(item, dict):
                lines += [f"- **UNVERIFIED — REQUIRES HUMAN REVIEW:** {_text(item.get('lead'))}" + (f" ({_source_note(item)})" if _source_note(item) else "")]
                if item.get("rationale"): lines.append(f"  - Rationale: {_text(item['rationale'])}")
            elif field == "key_claims" and isinstance(item, dict):
                lines.append(f"- **{_text(item.get('type', 'unclassified')).title()}:** {_text(item.get('claim'))}" + (f" ({_source_note(item)})" if _source_note(item) else ""))
                if item.get("excerpt"): lines.append(f"  - Supporting excerpt: “{_text(item['excerpt'])}”")
            else:
                lines.append(f"- {_text(item)}" + (f" ({_source_note(item)})" if _source_note(item) else ""))
        lines.append("")
    lines += ["## Methodology & Limitations", "", "Sarvam AI generated this structured analysis using only text supplied by the analyst. No independent source verification or external collection was performed. Classifications and confidence labels are model estimates, not calibrated probabilities. Leads are unverified and require human review before action.", "", "## Analyst Note", "", _text(analysis.get("analyst_note")) or "No analyst note provided.", ""]
    return "\n".join(lines)


def pdf_report(analysis, generated_at=None):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    except ImportError as exc:
        raise RuntimeError("PDF export requires ReportLab. Install dependencies from requirements.txt.") from exc
    stamp = generated_at or datetime.now().astimezone()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm, title="OSINT Fusion Workbench — Intelligence Dossier")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="DossierTitle", parent=styles["Title"], textColor=colors.HexColor("#12304a"), alignment=TA_LEFT, spaceAfter=8))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], textColor=colors.HexColor("#075985"), spaceBefore=12, spaceAfter=6, keepWithNext=True))
    styles.add(ParagraphStyle(name="BodySmall", parent=styles["BodyText"], fontSize=9, leading=13, spaceAfter=5, wordWrap="CJK"))
    story = [Paragraph("OSINT Fusion Workbench — Intelligence Dossier", styles["DossierTitle"]), Paragraph("Generated: " + xml_escape(stamp.strftime("%Y-%m-%d %H:%M:%S %Z")), styles["BodySmall"]), Spacer(1, 5), Paragraph("AI-generated from user-supplied text. Underlying claims have not been independently verified.", styles["BodySmall"])]
    def para(v): return Paragraph(xml_escape(_text(v)).replace("\n", "<br/>"), styles["BodySmall"])
    def section(title, entries):
        story.append(Paragraph(xml_escape(title), styles["Section"]))
        if not entries:
            story.append(para("None reported.")); return
        for entry in entries:
            story.append(para(entry))
    section("Source Inventory", [f"{_text(s.get('source_id'))} — {_text(s.get('filename'))} ({_text(s.get('characters'))} characters)" for s in analysis.get("sources", [])] or ["No source inventory supplied."])
    section("Extraction Warnings", analysis.get("extraction_warnings", []) or ["None."])
    section("Executive Summary", [analysis.get("executive_summary") or "No summary provided."])
    story.append(Paragraph("Entity Inventory", styles["Section"]))
    for cat in ENTITY_CATEGORIES:
        story.append(Paragraph(xml_escape(cat.title()), styles["Heading3"]))
        items = analysis.get("entities", {}).get(cat, [])
        story.append(para("; ".join(_text(i) + (f" ({_source_note(i)})" if _source_note(i) else "") for i in items) if items else "None reported."))
    section("Event Timeline", [f"{_text(i)}" + (f"\n{_source_note(i)}" if _source_note(i) else "") for i in analysis.get("timeline", [])])
    section("Relationships", [f"{_text(i)}" + (f"\n{_source_note(i)}" if _source_note(i) else "") for i in analysis.get("relationships", [])])
    section("Key Claims & Supporting Evidence", [f"{_text(i.get('type', 'unclassified')).title()}: {_text(i.get('claim'))}" + (f"\nExcerpt: {_text(i.get('excerpt'))}" if i.get("excerpt") else "") + (f"\n{_source_note(i)}" if _source_note(i) else "") if isinstance(i, dict) else i for i in analysis.get("key_claims", [])])
    section("Investigative Leads — UNVERIFIED — REQUIRES HUMAN REVIEW", [f"UNVERIFIED — REQUIRES HUMAN REVIEW: {_text(i.get('lead'))}" + (f"\nRationale: {_text(i.get('rationale'))}" if i.get("rationale") else "") if isinstance(i, dict) else i for i in analysis.get("investigative_leads", [])])
    section("Unanswered Questions", analysis.get("unanswered_questions", []))
    section("Uncertainty Warnings", analysis.get("uncertainty_warnings", []))
    section("Analyst Note", [analysis.get("analyst_note") or "No analyst note provided."])
    section("Methodology, Limitations & Human Review", ["This analysis was generated by AI from text supplied by the analyst. No external sources were consulted and no underlying claim has been independently verified. Confidence labels are model estimates, not calibrated probabilities. Investigative leads are unverified and require human review before action."])
    def footer(canvas, document):
        canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.grey)
        canvas.drawString(18*mm, 10*mm, "OSINT Fusion Workbench • AI-generated; human review required")
        canvas.drawRightString(A4[0]-18*mm, 10*mm, f"Page {document.page}"); canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
