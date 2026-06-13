from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from ..data.shariah_halal_terminal import (
    HALAL_TERMINAL_SOURCE_NAME,
    screen_symbol,
    status_to_row,
)
from ..data.shariah_sources import (
    DEFAULT_DB_PATH,
    DEFAULT_MANIFEST_PATH,
    load_manifest,
    load_source_rows,
    normalize_ticker,
    parse_source_as_of,
    upsert_source_row,
)
from ..models.shariah import ShariahStatus

DEFAULT_ACTIVE_SOURCES = ["spus_holdings"]

# Operator-curated Shariah inclusions: names asserted compliant by the operator
# that the external sources (SPUS / FTSE USA Shariah) omit because those indices
# only track larger caps. Applied server-side so they're compliant + in the
# universe regardless of browser/server-synced settings. A user exclusion still
# overrides these (status() checks exclusion first; _compliant_universe subtracts
# exclusions). Map ticker -> rationale note.
OPERATOR_CURATED_INCLUSIONS: dict[str, str] = {
    "LNTH": "Operator-asserted Shariah-compliant; not listed in SPUS/FTSE USA Shariah.",
}

KNOWN_CONFIGURABLE_SOURCES = {
    "spus_holdings",
    "spwo_holdings",
    "spre_holdings",
    "spte_holdings",
    "halal_terminal",
    "finispia",
}


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _active_sources(overrides: dict[str, Any] | None = None) -> list[str]:
    raw = (overrides or {}).get("active_sources")
    raw = raw or (overrides or {}).get("external_sources")
    raw = raw or (overrides or {}).get("shariah_external_sources")
    raw = raw or DEFAULT_ACTIVE_SOURCES
    if isinstance(raw, str):
        parts = raw.split(",")
    else:
        parts = list(raw)
    sources = [str(source).strip() for source in parts if str(source).strip()]
    return sources or list(DEFAULT_ACTIVE_SOURCES)


def _override_items(
    overrides: dict[str, Any] | None, keys: tuple[str, ...]
) -> list[Any]:
    source = overrides or {}
    for key in keys:
        if key in source:
            raw = source[key]
            if raw is None:
                return []
            if isinstance(raw, str):
                return [part.strip() for part in raw.split(",") if part.strip()]
            if isinstance(raw, list):
                return raw
    return []


def _override_map(items: Iterable[Any], direction: str) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, str):
            ticker = normalize_ticker(item)
            note = None
            added_at = None
        elif isinstance(item, dict):
            ticker = normalize_ticker(item.get("ticker") or item.get("symbol"))
            item_direction = item.get("direction")
            if item_direction and item_direction != direction:
                continue
            note = item.get("note") or item.get("rationale_note")
            added_at = item.get("added_at")
        else:
            continue
        if ticker:
            mapped[ticker] = {
                "ticker": ticker,
                "direction": direction,
                "note": note,
                "added_at": added_at,
            }
    return mapped


def normalize_shariah_overrides(overrides: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "active_sources": _active_sources(overrides),
        "inclusion": sorted(
            _override_map(
                _override_items(
                    overrides, ("inclusion", "include", "shariah_user_inclusion")
                ),
                "include",
            ).values(),
            key=lambda row: row["ticker"],
        ),
        "exclusion": sorted(
            _override_map(
                _override_items(
                    overrides, ("exclusion", "exclude", "shariah_user_exclusion")
                ),
                "exclude",
            ).values(),
            key=lambda row: row["ticker"],
        ),
    }


class ShariahLookup:
    def __init__(
        self,
        overrides: dict[str, Any] | None = None,
        *,
        db_path: Path | str = DEFAULT_DB_PATH,
        manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
        halal_terminal_api_key: str | None = None,
    ) -> None:
        normalized = normalize_shariah_overrides(overrides)
        self.active_sources = normalized["active_sources"]
        self.inclusion = {row["ticker"]: row for row in normalized["inclusion"]}
        self.exclusion = {row["ticker"]: row for row in normalized["exclusion"]}
        # Merge operator-curated inclusions, letting an explicit user inclusion
        # (with its own note) take precedence over the curated default.
        for ticker, note in OPERATOR_CURATED_INCLUSIONS.items():
            self.inclusion.setdefault(
                ticker,
                {"ticker": ticker, "direction": "include", "note": note, "added_at": None},
            )
        self.db_path = Path(db_path)
        self.manifest_path = Path(manifest_path)
        self.manifest = load_manifest(self.manifest_path)
        self.rows_by_ticker = load_source_rows(
            self.active_sources, db_path=self.db_path
        )
        self.halal_terminal_api_key = halal_terminal_api_key or os.getenv(
            "HALAL_TERMINAL_API_KEY"
        )
        self.stale_sources = self._stale_sources()

    def _source_is_stale(self, source_name: str) -> bool:
        meta = self.manifest.get("sources", {}).get(source_name)
        if not meta:
            if (
                source_name == HALAL_TERMINAL_SOURCE_NAME
                and self.halal_terminal_api_key
            ):
                return False
            return True
        if bool(meta.get("is_stale")):
            return True
        source_as_of = _parse_datetime(meta.get("source_as_of"))
        interval = int(meta.get("refresh_interval_days") or 7)
        if source_as_of is None:
            return True
        return datetime.now(timezone.utc) - source_as_of > timedelta(days=interval)

    def _source_unavailable(self, source_name: str) -> bool:
        meta = self.manifest.get("sources", {}).get(source_name)
        has_cached_rows = any(
            row["source_name"] == source_name
            for rows in self.rows_by_ticker.values()
            for row in rows
        )
        if source_name == HALAL_TERMINAL_SOURCE_NAME:
            return not (meta or has_cached_rows or self.halal_terminal_api_key)
        if source_name == "finispia":
            return not (
                meta
                or has_cached_rows
                or os.getenv("FINISPIA_EXPORT_PATH")
                or os.getenv("FINISPIA_EXPORT_URL")
            )
        return not (meta or has_cached_rows)

    def _stale_sources(self) -> list[str]:
        stale: list[str] = []
        for source_name in self.active_sources:
            if self._source_unavailable(source_name) or self._source_is_stale(
                source_name
            ):
                stale.append(source_name)
        return stale

    def _external_row(self, ticker: str) -> dict[str, Any] | None:
        rows = self.rows_by_ticker.get(ticker, [])
        if rows:
            by_source = {row["source_name"]: row for row in rows}
            for source_name in self.active_sources:
                if source_name in by_source:
                    return by_source[source_name]

        if (
            HALAL_TERMINAL_SOURCE_NAME in self.active_sources
            and self.halal_terminal_api_key
        ):
            payload = screen_symbol(ticker, self.halal_terminal_api_key)
            row = status_to_row(payload)
            if row is not None:
                upsert_source_row(row, db_path=self.db_path)
                mapped = {
                    "ticker": normalize_ticker(row["ticker"]),
                    "source_name": HALAL_TERMINAL_SOURCE_NAME,
                    "source_kind": "external",
                    "source_as_of": parse_source_as_of(row.get("source_as_of")),
                    "source_url": row.get("source_url"),
                }
                self.rows_by_ticker.setdefault(ticker, []).append(mapped)
                return mapped
        return None

    def status(self, ticker: str) -> ShariahStatus:
        symbol = normalize_ticker(ticker)
        included = self.inclusion.get(symbol)
        excluded = self.exclusion.get(symbol)
        conflict = included is not None and excluded is not None
        external = self._external_row(symbol)

        if excluded is not None:
            return ShariahStatus(
                ticker=symbol,
                is_compliant=False,
                source_kind="excluded_by_user",
                external_source_name=external.get("source_name") if external else None,
                external_source_as_of=(
                    external.get("source_as_of") if external else None
                ),
                is_stale=bool(
                    external and external.get("source_name") in self.stale_sources
                ),
                source_url=external.get("source_url") if external else None,
                user_note=excluded.get("note"),
                conflict=conflict,
                active_sources=self.active_sources,
            )

        if external is not None:
            return ShariahStatus(
                ticker=symbol,
                is_compliant=True,
                source_kind="external",
                external_source_name=external.get("source_name"),
                external_source_as_of=external.get("source_as_of"),
                is_stale=external.get("source_name") in self.stale_sources,
                source_url=external.get("source_url"),
                user_note=included.get("note") if included else None,
                conflict=conflict,
                active_sources=self.active_sources,
            )

        if included is not None:
            return ShariahStatus(
                ticker=symbol,
                is_compliant=True,
                source_kind="user",
                user_note=included.get("note"),
                conflict=conflict,
                active_sources=self.active_sources,
            )

        return ShariahStatus(
            ticker=symbol,
            is_compliant=False,
            source_kind="not_listed",
            conflict=conflict,
            active_sources=self.active_sources,
        )

    def statuses(self, tickers: Iterable[str]) -> dict[str, ShariahStatus]:
        return {normalize_ticker(ticker): self.status(ticker) for ticker in tickers}
