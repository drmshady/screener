from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from ..lib import flags
from ..models.sentiment import SpendLedger

DEFAULT_LEDGER_PATH = Path(__file__).resolve().parents[2] / "data" / "cache" / "spend.json"


class BudgetGuard:
    def __init__(
        self,
        path: str | Path = DEFAULT_LEDGER_PATH,
        *,
        cap_usd: Decimal | None = None,
        period: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.period = period or datetime.now(UTC).strftime("%Y-%m")
        self.cap_usd = cap_usd or Decimal(str(flags.sentiment_monthly_cap_usd()))

    def current(self) -> SpendLedger:
        if not self.path.exists():
            return SpendLedger(period=self.period, cap_usd=self.cap_usd)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("period") != self.period:
            return SpendLedger(period=self.period, cap_usd=self.cap_usd)
        ledger = SpendLedger.model_validate(payload)
        ledger.cap_usd = self.cap_usd
        return ledger

    def reserve_if_allowed(self, projected_cost: Decimal, *, cache_hit: bool = False) -> bool:
        if cache_hit or projected_cost <= 0:
            return True
        ledger = self.current()
        if ledger.estimated_spend_usd + projected_cost > ledger.cap_usd:
            return False
        ledger.estimated_spend_usd += projected_cost
        self._write(ledger)
        return True

    def _write(self, ledger: SpendLedger) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "period": ledger.period,
                    "estimated_spend_usd": str(ledger.estimated_spend_usd),
                    "cap_usd": str(ledger.cap_usd),
                },
                sort_keys=True,
                indent=2,
            ),
            encoding="utf-8",
        )
