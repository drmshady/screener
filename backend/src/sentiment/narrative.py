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
    # The no-directive guard governs the app's OWN generated copy, so validate only
    # the connective framing we author. The headlines are verbatim, attributed
    # third-party source material (rendered identically in the Sources list) and are
    # quoted, not recommended -- a publisher headline that says "Buy" must not crash
    # the whole report the way it did for analyst-heavy names (AMAT/BELFB).
    frame = f"{ticker.upper()} recent sourced context: "
    validate_no_directive_language(frame)
    return frame + "; ".join(parts) + "."


def validate_no_directive_language(text: str) -> None:
    lower = text.lower()
    for term in BANNED_DIRECTIVE_TERMS:
        if term in lower:
            raise DirectiveLanguageError(f"Directive language is not allowed: {term}")
