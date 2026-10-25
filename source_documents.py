"""In-memory extraction of analyst supplied PDF and text documents."""
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_UPLOAD_BYTES = 30 * 1024 * 1024
MAX_UPLOAD_FILES = 10
MAX_TOTAL_TEXT_CHARS = 100_000
PREVIEW_CHARS = 700
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


@dataclass
class ExtractedSource:
    source_id: str
    filename: str
    text: str
    page_count: int | None = None

    def metadata(self):
        return {"source_id": self.source_id, "filename": self.filename,
                "page_count": self.page_count, "characters": len(self.text)}


def extract_document(filename, content, source_id="SRC-01"):
    """Extract one supported upload; returns source and non-fatal extraction warnings."""
    name = PurePath(str(filename or "uploaded-file").replace("\\", "/")).name
    suffix = PurePath(name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"{name}: unsupported file type. Use PDF, TXT, or Markdown (.md).")
    if not isinstance(content, bytes):
        content = bytes(content)
    if len(content) > MAX_FILE_BYTES:
        raise ValueError(f"{name}: file exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MB per-file limit.")
    if not content:
        raise ValueError(f"{name}: file is empty.")

    warnings = []
    page_count = None
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            document = PdfReader(BytesIO(content), strict=True)
            if document.is_encrypted:
                raise ValueError(f"{name}: PDF is encrypted and cannot be read without a password.")
            page_count = len(document.pages)
            chunks = []
            text_pages = 0
            for index, page in enumerate(document.pages, start=1):
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    text_pages += 1
                    chunks.append(f"[Page {index}]\n{page_text}")
            if not chunks:
                raise ValueError(f"{name}: PDF has no selectable text (it may be scanned or image-only).")
            if text_pages < page_count:
                warnings.append(f"{name}: selectable text was found on {text_pages} of {page_count} pages; other pages may be scanned or blank.")
            text = "\n\n".join(chunks)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"{name}: PDF could not be read ({type(exc).__name__}).") from exc
    else:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="replace")
            warnings.append(f"{name}: invalid UTF-8 sequences were replaced with the replacement character.")
        if not text.strip():
            raise ValueError(f"{name}: file contains no readable text.")

    if not text.strip():
        raise ValueError(f"{name}: no readable text could be extracted.")
    if len(text) > MAX_TOTAL_TEXT_CHARS:
        raise ValueError(f"{name}: extracted text exceeds the {MAX_TOTAL_TEXT_CHARS:,}-character limit; no text was truncated.")
    return ExtractedSource(source_id, name, text, page_count), warnings


def combine_sources(sources, pasted_text="", pasted_filename="Pasted text"):
    """Format a bounded, source-labelled prompt input; never silently truncate."""
    all_sources = list(sources)
    if pasted_text and pasted_text.strip():
        all_sources.insert(0, ExtractedSource("PASTED-01", pasted_filename, pasted_text.strip()))
    total = sum(len(s.text) for s in all_sources)
    if total > MAX_TOTAL_TEXT_CHARS:
        raise ValueError(f"Combined extracted text is {total:,} characters; the limit is {MAX_TOTAL_TEXT_CHARS:,}. Remove sources or reduce the supplied text. No text was truncated.")
    parts = []
    for source in all_sources:
        parts.append(f"--- SOURCE {source.source_id} | FILENAME: {source.filename} ---\n{source.text}\n--- END SOURCE {source.source_id} ---")
    return "\n\n".join(parts), all_sources


def source_preview(source, max_chars=PREVIEW_CHARS):
    preview = source.text[:max_chars]
    return preview + ("… [preview clipped]" if len(source.text) > max_chars else "")


def validate_attributions(analysis, sources):
    """Remove unsupported model citations/page numbers/quoted excerpts and return warnings."""
    by_id = {source.source_id: source for source in sources}
    warnings = []
    row_fields = ("people", "organizations", "locations", "dates", "technologies",
                  "timeline", "relationships", "key_claims", "investigative_leads")
    for field in row_fields:
        rows = (analysis.get("entities", {}).get(field, []) if field in {"people", "organizations", "locations", "dates", "technologies"}
                else analysis.get(field, []))
        for row in rows:
            if not isinstance(row, dict):
                continue
            if isinstance(row.get("source_id"), str) and row["source_id"] not in by_id:
                warnings.append(f"Removed an unsupported source ID from {field}.")
                row.pop("source_id", None)
            if "source_ids" in row:
                raw_ids = row.get("source_ids")
                raw_ids = [raw_ids] if isinstance(raw_ids, str) else raw_ids
                if isinstance(raw_ids, list):
                    valid_ids = [source_id for source_id in raw_ids if isinstance(source_id, str) and source_id in by_id]
                    if len(valid_ids) != len(raw_ids):
                        warnings.append(f"Removed unsupported source IDs from {field}.")
                    if valid_ids:
                        row["source_ids"] = valid_ids
                    else:
                        row.pop("source_ids", None)
            cited_id = row.get("source_id")
            if not isinstance(cited_id, str):
                cited_id = None
            row.pop("source_filenames", None)
            if "page" in row:
                source = by_id.get(cited_id)
                page = row.get("page")
                if not source or source.page_count is None or not isinstance(page, int) or not (1 <= page <= source.page_count):
                    warnings.append(f"Removed a page reference that could not be verified in {field}.")
                    row.pop("page", None)
            for excerpt_key in ("excerpt", "source_excerpt"):
                excerpt = row.get(excerpt_key)
                if not excerpt:
                    continue
                candidates = [by_id[cited_id]] if cited_id and cited_id in by_id else list(by_id.values())
                normalized_excerpt = " ".join(str(excerpt).split())
                if not any(normalized_excerpt in " ".join(source.text.split()) for source in candidates):
                    warnings.append(f"Removed a {excerpt_key.replace('_', ' ')} that did not match supplied source text.")
                    row.pop(excerpt_key, None)
            attribution_ids = row.get("source_ids") or ([cited_id] if cited_id and cited_id in by_id else [])
            if attribution_ids:
                row["source_filenames"] = list(dict.fromkeys(by_id[source_id].filename for source_id in attribution_ids))
    return warnings
