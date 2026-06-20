"""Trading-day / new-session guard for the US1 automated daily refresh (FR-005).

Short-circuits the whole publish chain when the latest completed trading
session is not newer than what is already published, so non-trading days
(and a same-day re-run) cost no refresh/build/push/rebuild and never regress
`data_as_of` (contracts/daily-automation.md).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.src.data.market_calendar import latest_completed_trading_day  # noqa: E402

GuardOutcome = Literal["proceed", "noop"]


@dataclass(frozen=True)
class GuardDecision:
    outcome: GuardOutcome
    latest_session: date
    published_data_as_of: date | None
    reason: str


def resolve_guard_decision(
    latest_session: date, published_data_as_of: date | None
) -> GuardDecision:
    """Pure decision: `noop` unless `latest_session` is strictly newer than
    `published_data_as_of` (or nothing has been published yet)."""
    if published_data_as_of is not None and latest_session <= published_data_as_of:
        return GuardDecision(
            outcome="noop",
            latest_session=latest_session,
            published_data_as_of=published_data_as_of,
            reason=(
                f"latest completed session {latest_session.isoformat()} is not newer "
                f"than published data_as_of {published_data_as_of.isoformat()}"
            ),
        )
    return GuardDecision(
        outcome="proceed",
        latest_session=latest_session,
        published_data_as_of=published_data_as_of,
        reason=(
            f"latest completed session {latest_session.isoformat()} is newer than "
            "published data_as_of "
            f"{published_data_as_of.isoformat() if published_data_as_of else 'unknown'}"
        ),
    )


def published_data_as_of_from_manifest(path: Path) -> date | None:
    """Read the published `data_as_of` from a (currently-live) manifest.json.

    No exceptions on a missing/corrupt manifest -- treated as "nothing
    published yet" so the guard fails open to `proceed` rather than blocking
    the very first run.
    """
    if not path.exists():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    sources = manifest.get("sources", {})
    prices = sources.get("yfinance") if isinstance(sources, dict) else None
    if not isinstance(prices, dict):
        return None
    by_ticker = prices.get("last_bar_date_by_ticker")
    if not isinstance(by_ticker, dict) or not by_ticker:
        return None
    dates = []
    for value in by_ticker.values():
        try:
            dates.append(datetime.fromisoformat(str(value)).date())
        except ValueError:
            continue
    return max(dates) if dates else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--published-manifest",
        type=Path,
        help="Path to the currently-published manifest.json (e.g. extracted "
        "from the running image with `docker run --rm <image> cat "
        "/app/backend/data/manifest.json`).",
    )
    parser.add_argument(
        "--published-data-as-of",
        help="Published data_as_of as an ISO date; overrides --published-manifest.",
    )
    parser.add_argument("--market", default="US")
    args = parser.parse_args(argv)

    if args.published_data_as_of:
        published = datetime.fromisoformat(args.published_data_as_of).date()
    elif args.published_manifest:
        published = published_data_as_of_from_manifest(args.published_manifest)
    else:
        published = None

    latest_session = latest_completed_trading_day(market=args.market)
    decision = resolve_guard_decision(latest_session, published)
    print(f"[session-guard] {decision.reason}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"outcome={decision.outcome}\n")
            fh.write(f"latest_session={decision.latest_session.isoformat()}\n")

    print(decision.outcome)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
