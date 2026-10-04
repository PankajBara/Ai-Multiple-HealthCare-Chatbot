"""Shared citation and provenance helpers.

The API deliberately keeps source records structured so clients can render them
without scraping answer text.  URLs are treated as untrusted input and only
HTTP(S) links are exposed as clickable sources.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse


SOURCE_KEYS = ("title", "url", "source_type")


def is_safe_url(url: Any) -> bool:
    if not isinstance(url, str) or not url:
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def normalize_sources(sources: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Normalize, sanitize and deduplicate source records."""
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for raw in sources or []:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or raw.get("source") or "Untitled source").strip()
        url = str(raw.get("url") or raw.get("path") or "").strip()
        source_type = str(raw.get("source_type") or "Unknown").strip()
        # Keep non-link provenance (for example local model metadata), while
        # never allowing unsafe URLs to become clickable links.
        key = url.lower() if url else f"{source_type.lower()}:{title.lower()}"
        if key in seen:
            continue
        seen.add(key)
        item: Dict[str, Any] = {
            "title": title,
            "url": url if is_safe_url(url) else "",
            "source_type": source_type,
        }
        for field in ("journal", "publication_date", "relevance", "confidence", "model_name", "model_version"):
            if raw.get(field) is not None and raw.get(field) != "":
                item[field] = raw[field]
        if raw.get("notice"):
            item["notice"] = str(raw["notice"])
        normalized.append(item)
    return normalized


def add_inline_citations(text: Any, sources: Optional[List[Dict[str, Any]]]) -> str:
    """Append inspectable markers for grounded sources without duplicating them."""
    value = text.content if hasattr(text, "content") else str(text or "")
    safe_sources = normalize_sources(sources)
    if not safe_sources:
        return value
    markers = " ".join(f"[{idx}]" for idx in range(1, len(safe_sources) + 1))
    # Do not add a second marker set when an upstream generator already did so.
    if re.search(r"\[\d+\]", value):
        return value
    return f"{value.rstrip()} {markers}".strip()


def factual_query(query: str) -> bool:
    """Conservative detector used to skip PubMed for greetings/small talk."""
    text = (query or "").strip().lower()
    if not text:
        return False
    if re.match(r"^(hi|hello|hey|hiya|good morning|good afternoon|good evening)\b", text):
        return False
    if re.search(r"\b(thanks|thank you|thx|how are you|who are you|nice to meet|goodbye|bye)\b", text):
        return False
    return bool(re.search(
        r"\b(symptom|disease|medical|medicine|health|diagnos|treatment|drug|dose|covid|cancer|tumou?r|diabet|fever|pain|lesion|x.?ray|mri|infection|vaccine|blood|skin|lung|heart|headache|pregnan)\b",
        text,
    ))


def pubmed_sources(agent: Any, query: str, retmax: int = 3) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Fetch PubMed records while converting failures into a visible notice."""
    try:
        records = agent.search_pubmed_records(query, retmax=retmax)
        if isinstance(records, str):
            return [], "Supporting literature unavailable: PubMed could not be reached."
        records = normalize_sources(records)
        if not records:
            return [], "Supporting literature unavailable: no matching PubMed records were found."
        return records, None
    except Exception:
        return [], "Supporting literature unavailable: PubMed could not be reached."
