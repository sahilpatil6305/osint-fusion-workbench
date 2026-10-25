"""OSINT Fusion Workbench Streamlit interface."""
from datetime import datetime
import json

import streamlit as st

from reports import ENTITY_CATEGORIES, json_bytes, markdown_report, normalize_analysis, pdf_report
from sarvam_client import analyze_text
from source_documents import (extract_document, combine_sources, source_preview,
                              validate_attributions, MAX_UPLOAD_FILES,
                              MAX_TOTAL_UPLOAD_BYTES)

st.set_page_config(page_title="OSINT Fusion Workbench", page_icon="🔎", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@400;500;600;700&display=swap');
.stApp {background:#09111d;color:#d6e2f0} [data-testid="stHeader"]{background:#09111d}
html,body,[class*="css"]{font-family:Inter,sans-serif}
.block-container{padding-top:1.7rem;max-width:1440px}
.hero{padding:1.35rem 1.6rem;margin-bottom:1rem;border:1px solid #203b56;border-radius:12px;background:linear-gradient(120deg,#10263a,#0c1725 65%)}
.hero h1{margin:0;color:#65d7ed;font:600 1.45rem 'IBM Plex Mono',monospace;letter-spacing:.04em}
.hero p{margin:.4rem 0 0;color:#9db3c9;font-size:.92rem}
[data-testid="stMetric"]{background:#0e1c2b;border:1px solid #203b56;padding:1rem;border-radius:10px}
[data-testid="stMetricLabel"]{color:#a6bdd2}
.stButton button,.stDownloadButton button{border-radius:7px;font-weight:600}
hr{border-color:#203b56}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>⬡ OSINT FUSION WORKBENCH</h1><p>Structured analysis of analyst-supplied public reporting · Leads require human review</p></div>', unsafe_allow_html=True)
st.caption("API status: not checked · Analysis uses only the text you submit; no external data is fetched.")

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "analysis_error" not in st.session_state:
    st.session_state.analysis_error = None
if "upload_generation" not in st.session_state:
    st.session_state.upload_generation = 0

st.subheader("Source documents")
st.caption("Upload PDF, TXT, or Markdown files. Files are processed in memory and are not saved by the app.")
uploads = st.file_uploader("Attach source documents", type=["pdf", "txt", "md"], accept_multiple_files=True,
                          key=f"source_upload_{st.session_state.upload_generation}",
                          help="Up to 10 files, 10 MB each, 30 MB total upload size, and 100,000 combined extracted characters.")
extracted_uploads = []
upload_warnings = []
if uploads:
    clear_col, _ = st.columns([1, 3])
    with clear_col:
        if st.button("Clear uploaded files", key="clear_source_uploads"):
            st.session_state.upload_generation += 1
            st.rerun()
    st.markdown("**Review attached files** · Uncheck files to exclude them from this analysis.")
    if len(uploads) > MAX_UPLOAD_FILES:
        upload_warnings.append(f"Only the first {MAX_UPLOAD_FILES} files are available for this analysis.")
    accepted_uploads = uploads[:MAX_UPLOAD_FILES]
    total_upload_bytes = 0
    for index, uploaded in enumerate(accepted_uploads):
        if total_upload_bytes + uploaded.size > MAX_TOTAL_UPLOAD_BYTES:
            upload_warnings.append(f"{uploaded.name}: skipped because the combined upload-size limit is {MAX_TOTAL_UPLOAD_BYTES // (1024 * 1024)} MB.")
            continue
        total_upload_bytes += uploaded.size
        source_id = f"SRC-{index + 1:02d}"
        try:
            source, warnings = extract_document(uploaded.name, uploaded.getvalue(), source_id)
            upload_warnings.extend(warnings)
            include = st.checkbox(f"Include {source.filename} · {len(source.text):,} extracted characters", value=True,
                                  key=f"include_{st.session_state.upload_generation}_{index}_{uploaded.name}_{uploaded.size}")
            with st.expander(f"Preview · {source.filename}", expanded=False):
                st.caption(f"Source ID: {source.source_id}" + (f" · {source.page_count} pages" if source.page_count is not None else ""))
                st.text(source_preview(source))
            if include:
                extracted_uploads.append(source)
        except ValueError as exc:
            upload_warnings.append(str(exc))
    for warning in upload_warnings:
        st.warning(warning)

article = st.text_area("Paste source text (optional)", height=190, placeholder="Paste a public news article, security advisory, or incident report…", key="article_text")
left, right = st.columns([1, 3])
with left:
    analyze_clicked = st.button("Analyze with Sarvam", type="primary", use_container_width=True)
with right:
    st.caption("The supplied text is treated as untrusted input and is not used as application instructions.")

if analyze_clicked:
    try:
        prompt_text, submitted_sources = combine_sources(extracted_uploads, article)
        if not prompt_text:
            st.warning("Attach at least one readable source or paste text before analyzing.")
        else:
            with st.spinner("Analyzing supplied sources…"):
                new_result = normalize_analysis(analyze_text(prompt_text))
            new_result["sources"] = [source.metadata() for source in submitted_sources]
            new_result["extraction_warnings"] = list(upload_warnings) + validate_attributions(new_result, submitted_sources)
            st.session_state.analysis_result = new_result
            st.session_state.analysis_error = None
    except EnvironmentError:
        st.session_state.analysis_error = "SARVAM_API_KEY is not configured. Set it in the local .env file and restart the app."
    except ValueError as exc:
        st.session_state.analysis_error = str(exc)
    except Exception as exc:
        st.session_state.analysis_error = f"Analysis request failed ({type(exc).__name__}). Check connectivity and SDK configuration, then retry."

if st.session_state.analysis_error:
    st.error(st.session_state.analysis_error)

result = st.session_state.analysis_result
if result:
    for warning in result.get("extraction_warnings", []):
        st.warning(warning)
    st.divider()
    st.subheader("Intelligence report")
    entity_count = sum(len(result.get("entities", {}).get(cat, [])) for cat in ENTITY_CATEGORIES)
    metrics = st.columns(4)
    for col, label, value in zip(metrics, ("Entities", "Timeline events", "Key claims", "Investigative leads"), (entity_count, len(result["timeline"]), len(result["key_claims"]), len(result["investigative_leads"]))):
        col.metric(label, value)

    tabs = st.tabs(["Executive Summary", "Entity Intelligence", "Event Timeline", "Relationships", "Claims & Evidence", "Investigative Leads", "Unanswered Questions"])
    with tabs[0]:
        st.markdown(result.get("executive_summary") or "No executive summary was returned.")
        if result.get("uncertainty_warnings"):
            st.warning("Review uncertainty warnings")
            for warning in result["uncertainty_warnings"]: st.write("•", warning)
        st.info(result.get("analyst_note") or "AI-generated analysis; underlying claims have not been independently verified.")
    with tabs[1]:
        entities = result["entities"]
        for category in ENTITY_CATEGORIES:
            with st.expander(category.replace("_", " ").title(), expanded=bool(entities[category])):
                if entities[category]: st.dataframe(entities[category], use_container_width=True, hide_index=True)
                else: st.caption("No entries reported.")
    with tabs[2]:
        if result["timeline"]: st.dataframe(result["timeline"], use_container_width=True, hide_index=True)
        else: st.caption("No timeline events reported.")
    with tabs[3]:
        if result["relationships"]: st.dataframe(result["relationships"], use_container_width=True, hide_index=True)
        else: st.caption("No relationships reported.")
    with tabs[4]:
        if result["key_claims"]:
            for claim in result["key_claims"]:
                if isinstance(claim, dict):
                    st.markdown(f"**{str(claim.get('type', 'unclassified')).title()}** · {claim.get('claim', '')}")
                    if claim.get("excerpt"): st.caption(f"Supporting excerpt: “{claim['excerpt']}”")
                    source_ids = claim.get("source_ids") or ([claim["source_id"]] if claim.get("source_id") else [])
                    source_files = claim.get("source_filenames") or []
                    if isinstance(source_ids, str): source_ids = [source_ids]
                    if isinstance(source_files, str): source_files = [source_files]
                    if source_ids or source_files:
                        citation = "Sources: " + ", ".join(str(value) for value in source_ids + source_files)
                        if claim.get("page") is not None: citation += f" · page {claim['page']}"
                        st.caption(citation)
                    st.caption("Confidence label is a model estimate, not a calibrated probability.")
                    st.divider()
                else: st.write(claim)
        else: st.caption("No claims reported.")
    with tabs[5]:
        if result["investigative_leads"]:
            for lead in result["investigative_leads"]:
                st.warning("UNVERIFIED — REQUIRES HUMAN REVIEW")
                if isinstance(lead, dict):
                    st.markdown(f"**{lead.get('lead', '')}**")
                    if lead.get("rationale"): st.write(lead["rationale"])
                    if lead.get("source_filenames"):
                        st.caption("Sources: " + ", ".join(lead["source_filenames"]))
                else: st.write(lead)
        else: st.caption("No investigative leads reported.")
    with tabs[6]:
        if result["unanswered_questions"]:
            for question in result["unanswered_questions"]: st.markdown(f"- {question}")
        else: st.caption("No unanswered questions reported.")

    with st.expander("Uncertainty warnings and analyst note"):
        if result["uncertainty_warnings"]:
            for warning in result["uncertainty_warnings"]: st.warning(warning)
        else: st.caption("No uncertainty warnings returned.")
        st.write(result.get("analyst_note") or "No analyst note returned.")
    with st.expander("Raw JSON"):
        st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")

    st.divider()
    st.subheader("Download Intelligence Report")
    st.caption("Exports use the latest successful analysis already in this session; downloading does not call Sarvam.")
    generated = datetime.now().astimezone()
    date_label = generated.strftime("%Y-%m-%d")
    try:
        pdf_data = pdf_report(result, generated)
        md_data = markdown_report(result, generated).encode("utf-8")
        json_data = json_bytes(result)
        p, j, m = st.columns(3)
        p.download_button("Download PDF dossier", pdf_data, f"osint_report_{date_label}.pdf", "application/pdf", use_container_width=True)
        j.download_button("Download JSON", json_data, f"osint_report_{date_label}.json", "application/json", use_container_width=True)
        m.download_button("Download Markdown", md_data, f"osint_report_{date_label}.md", "text/markdown; charset=utf-8", use_container_width=True)
    except RuntimeError as exc:
        st.error(str(exc))
