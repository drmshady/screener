from __future__ import annotations

from ..models.sentiment import SourceItem

BANNED_DIRECTIVE_TERMS = (
    "strong buy",
    "should buy",
    "buy",
    "sell",
    "recommended",
)


class DirectiveLanguageError(ValueError):
    pass


def build_template_narrative(ticker: str, sources: list[SourceItem], *, max_items: int = 3) -> str:
    if not sources:
        return f"{ticker.upper()} has no qualifying sourced sentiment items in the current capture."
    ordered = sorted(sources, key=lambda item: (item.published_at, item.id), reverse=True)[:max_items]
    parts = []
    for item in ordered:
        publisher = item.publisher or item.source_class.value
        date = item.published_at.date().isoformat()
        stale = " stale" if item.is_stale else ""
        parts.append(f"{publisher} on {date}{stale}: {item.title}")
    narrative = f"{ticker.upper()} recent sourced context: " + "; ".join(parts) + "."
    validate_no_directive_language(narrative)
    return narrative


def validate_no_directive_language(text: str) -> None:
    lower = text.lower()
    for term in BANNED_DIRECTIVE_TERMS:
        if term in lower:
            raise DirectiveLanguageError(f"Directive language is not allowed: {term}")
