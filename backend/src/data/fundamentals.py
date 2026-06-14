from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from ..models.catalog import FormType, FundamentalsSnapshot

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
DEFAULT_UA = "screener-local-audit contact@example.com"


class FundamentalsLoader:
    def __init__(self, user_agent: str = DEFAULT_UA):
        self.headers = {"User-Agent": user_agent}
        self._cik_map: dict[str, str] | None = None

    def _load_cik_map(self) -> dict[str, str]:
        if self._cik_map is None:
            response = httpx.get(SEC_COMPANY_TICKERS_URL, headers=self.headers, timeout=30)
            response.raise_for_status()
            self._cik_map = {
                row["ticker"].upper(): str(row["cik_str"]).zfill(10)
                for row in response.json().values()
            }
        return self._cik_map

    def cik_for_ticker(self, ticker: str) -> str:
        cik = self._load_cik_map().get(ticker.upper())
        if cik is None:
            raise ValueError(f"Ticker {ticker.upper()} not found in SEC company_tickers.json")
        return cik

    def fetch_company_facts(self, ticker: str) -> dict[str, Any]:
        cik = self.cik_for_ticker(ticker)
        response = httpx.get(SEC_COMPANY_FACTS_URL.format(cik=cik), headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _facts(payload: dict[str, Any], tag: str) -> list[dict[str, Any]]:
        units = payload.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {})
        return units.get("USD", []) or units.get("shares", []) or []

    @staticmethod
    def _ns_facts(payload: dict[str, Any], namespace: str, tag: str) -> list[dict[str, Any]]:
        """Facts for a tag under an arbitrary taxonomy namespace (e.g. ``dei``).
        Share counts on modern filers live under ``dei``, not ``us-gaap``."""
        units = payload.get("facts", {}).get(namespace, {}).get(tag, {}).get("units", {})
        return units.get("shares", []) or units.get("USD", []) or []

    # Max age (days) between a share count's period end and the as-of date before
    # the count is considered stale. Pairing a years-old share count with current
    # financials produces a wildly wrong market cap (the RTX 2009-shares bug), so
    # a stale count is treated as missing rather than silently used.
    _SHARES_MAX_STALE_DAYS = 450

    def _shares_outstanding_as_of(
        self, payload: dict[str, Any], as_of: date
    ) -> float | None:
        """Most recent reliable common-share count known on or before ``as_of``.

        Prefers the dei cover-page count ``EntityCommonStockSharesOutstanding``
        (full actual shares, reported on every 10-K/10-Q by modern filers), then
        falls back to the us-gaap balance-sheet concepts. Any count whose period
        end is more than ``_SHARES_MAX_STALE_DAYS`` before ``as_of`` is rejected
        as stale (returns None) — never paired with newer financials.
        """
        sources = (
            ("dei", "EntityCommonStockSharesOutstanding"),
            # The slim EDGAR cache stores this concept under us-gaap, so check there
            # too (some companyfacts payloads also mirror the dei cover-page count).
            ("us-gaap", "EntityCommonStockSharesOutstanding"),
            ("us-gaap", "CommonStockSharesOutstanding"),
            ("us-gaap", "CommonStockSharesIssued"),
        )
        for namespace, tag in sources:
            rows = [
                row
                for row in self._ns_facts(payload, namespace, tag)
                if row.get("end")
                and row.get("filed")
                and row.get("val") is not None
                and date.fromisoformat(row["filed"]) <= as_of
            ]
            if not rows:
                continue
            row = sorted(rows, key=lambda r: (r["end"], r["filed"]))[-1]
            period_end = date.fromisoformat(row["end"])
            if (as_of - period_end).days > self._SHARES_MAX_STALE_DAYS:
                # This source only has a stale count; try the next source before
                # giving up (a newer source may still carry a current count).
                continue
            return float(row["val"])
        return None

    @staticmethod
    def _latest_by_period(payload: dict[str, Any], tag: str, form: str) -> dict[str, Any] | None:
        rows = [
            row
            for row in FundamentalsLoader._facts(payload, tag)
            if row.get("form") == form and row.get("end") and row.get("filed") and row.get("val") is not None
        ]
        if not rows:
            return None
        return sorted(rows, key=lambda row: (row["end"], row["filed"]))[-1]

    @staticmethod
    def _latest_as_of(
        payload: dict[str, Any], tag: str, as_of: date, form: str = "10-K"
    ) -> dict[str, Any] | None:
        """
        Point-in-time selector: the row with the most recent period end among
        filings actually *filed on or before* `as_of`. This is what enforces
        no look-ahead in a backtest — a value reported in a later filing is
        invisible at the as-of date.
        """
        rows = [
            row
            for row in FundamentalsLoader._facts(payload, tag)
            if row.get("form") == form
            and row.get("end")
            and row.get("filed")
            and row.get("val") is not None
            and date.fromisoformat(row["filed"]) <= as_of
        ]
        if not rows:
            return None
        return sorted(rows, key=lambda row: (row["end"], row["filed"]))[-1]

    @staticmethod
    def _decimal(row: dict[str, Any] | None) -> Decimal:
        if row is None:
            return Decimal("0")
        return Decimal(str(row["val"]))

    def fetch_fundamentals(self, ticker: str, start_date: date | None = None) -> list[FundamentalsSnapshot]:
        payload = self.fetch_company_facts(ticker)
        cik = str(payload.get("cik", "")).zfill(10)
        now = datetime.now(timezone.utc)
        snapshots: list[FundamentalsSnapshot] = []
        for form_type in (FormType.FORM_10_K, FormType.FORM_10_Q):
            form = form_type.value
            revenue = self._latest_by_period(payload, "Revenues", form) or self._latest_by_period(payload, "RevenueFromContractWithCustomerExcludingAssessedTax", form)
            net_income = self._latest_by_period(payload, "NetIncomeLoss", form)
            assets = self._latest_by_period(payload, "Assets", form)
            liabilities = self._latest_by_period(payload, "Liabilities", form)
            shares = self._latest_by_period(payload, "EntityCommonStockSharesOutstanding", form)
            anchor = revenue or net_income or assets
            if anchor is None:
                continue
            period_end = date.fromisoformat(anchor["end"])
            filing_date = date.fromisoformat(anchor["filed"])
            if start_date and filing_date < start_date:
                continue
            snapshots.append(
                FundamentalsSnapshot(
                    ticker=ticker.upper(),
                    period_end=period_end,
                    filing_date=filing_date,
                    form_type=form_type,
                    revenue=self._decimal(revenue),
                    eps_basic=Decimal("0"),
                    eps_diluted=Decimal("0"),
                    net_income=self._decimal(net_income),
                    total_assets=self._decimal(assets),
                    total_liabilities=self._decimal(liabilities),
                    shares_outstanding=self._decimal(shares),
                    accession_number=str(anchor.get("accn", "")),
                    source_name="sec_edgar_companyfacts",
                    source_as_of=now,
                )
            )
        return snapshots

    def quality_metrics(self, ticker: str) -> dict[str, Decimal | None]:
        payload = self.fetch_company_facts(ticker)
        operating_cf = self._latest_by_period(payload, "NetCashProvidedByUsedInOperatingActivities", "10-K")
        capex = self._latest_by_period(payload, "PaymentsToAcquirePropertyPlantAndEquipment", "10-K")
        liabilities = self._latest_by_period(payload, "Liabilities", "10-K")
        equity = self._latest_by_period(payload, "StockholdersEquity", "10-K")
        fcf = None
        if operating_cf is not None and capex is not None:
            fcf = self._decimal(operating_cf) - self._decimal(capex)
        debt_to_equity = None
        if liabilities is not None and equity is not None and self._decimal(equity) != 0:
            debt_to_equity = self._decimal(liabilities) / self._decimal(equity)
        return {"fcf_ttm": fcf, "debt_to_equity": debt_to_equity}

    def _gross_profit_as_of(self, payload: dict[str, Any], as_of: date) -> Decimal | None:
        """GrossProfit if reported, else Revenue - Cost of Revenue (Novy-Marx numerator)."""
        gross = self._latest_as_of(payload, "GrossProfit", as_of)
        if gross is not None:
            return self._decimal(gross)
        revenue = self._latest_as_of(payload, "Revenues", as_of) or self._latest_as_of(
            payload, "RevenueFromContractWithCustomerExcludingAssessedTax", as_of
        )
        cogs = self._latest_as_of(payload, "CostOfRevenue", as_of) or self._latest_as_of(
            payload, "CostOfGoodsAndServicesSold", as_of
        )
        if revenue is None or cogs is None:
            return None
        return self._decimal(revenue) - self._decimal(cogs)

    def _annual_assets_as_of(
        self, payload: dict[str, Any], as_of: date, form: str = "10-K"
    ) -> list[Decimal]:
        """Annual total-Assets values (ascending by period end) from filings filed
        on or before `as_of`, deduped to the latest filing per period end. Used to
        derive year-over-year asset growth (George-Hwang-Lin / Hou-Xue-Zhang)."""
        rows = [
            row
            for row in self._facts(payload, "Assets")
            if row.get("form") == form
            and row.get("end")
            and row.get("filed")
            and row.get("val") is not None
            and date.fromisoformat(row["filed"]) <= as_of
        ]
        by_end: dict[str, dict[str, Any]] = {}
        for row in sorted(rows, key=lambda r: (r["end"], r["filed"])):
            by_end[row["end"]] = row  # later filing for the same period end wins
        return [Decimal(str(by_end[end]["val"])) for end in sorted(by_end.keys())]

    def _annual_values_as_of(
        self, payload: dict[str, Any], tag: str, as_of: date, form: str = "10-K"
    ) -> list[Decimal]:
        """Annual values for one concept (ascending by period end) from filings
        filed on or before `as_of`, deduped to the latest filing per period end.
        Generalizes `_annual_assets_as_of` to any tag. Enforces no look-ahead."""
        rows = [
            row
            for row in self._facts(payload, tag)
            if row.get("form") == form
            and row.get("end")
            and row.get("filed")
            and row.get("val") is not None
            and date.fromisoformat(row["filed"]) <= as_of
        ]
        by_end: dict[str, dict[str, Any]] = {}
        for row in sorted(rows, key=lambda r: (r["end"], r["filed"])):
            by_end[row["end"]] = row  # later filing for the same period end wins
        return [Decimal(str(by_end[end]["val"])) for end in sorted(by_end.keys())]

    def _annual_revenue_as_of(
        self, payload: dict[str, Any], as_of: date
    ) -> list[Decimal]:
        """Revenue annual series, preferring `Revenues` then the contract-revenue
        tag (matches the fallbacks used elsewhere in this loader)."""
        series = self._annual_values_as_of(payload, "Revenues", as_of)
        if series:
            return series
        return self._annual_values_as_of(
            payload, "RevenueFromContractWithCustomerExcludingAssessedTax", as_of
        )

    def value_metrics_as_of(
        self, ticker: str, as_of: date, payload: dict[str, Any] | None = None
    ) -> dict[str, float | None]:
        """Point-in-time inputs for the value-composite yields AND the nine
        Piotroski signals, using only EDGAR filings filed on or before `as_of`.

        Returns the latest annual value of each concept plus its prior-year value
        (prefixed ``prior_``) so the F-Score deltas can be computed. Every value is
        a plain ``float`` or ``None`` (missing on/before the as-of date — never
        fabricated). Market cap is NOT computed here (it needs the live price); the
        caller multiplies ``shares_outstanding`` by the close.
        """
        payload = payload if payload is not None else self.fetch_company_facts(ticker)

        # (current, prior) annual value for one concept, with optional fallback tags.
        def pair(*tags: str) -> tuple[float | None, float | None]:
            series: list[Decimal] = []
            for tag in tags:
                series = self._annual_values_as_of(payload, tag, as_of)
                if series:
                    break
            current = float(series[-1]) if len(series) >= 1 else None
            prior = float(series[-2]) if len(series) >= 2 else None
            return current, prior

        equity, prior_equity = pair("StockholdersEquity")
        net_income, prior_net_income = pair("NetIncomeLoss")
        operating_cf, prior_operating_cf = pair(
            "NetCashProvidedByUsedInOperatingActivities"
        )
        assets, prior_assets = pair("Assets")
        gross_profit, prior_gross_profit = pair("GrossProfit")
        current_assets, prior_current_assets = pair("AssetsCurrent")
        current_liabilities, prior_current_liabilities = pair("LiabilitiesCurrent")
        long_term_debt, prior_long_term_debt = pair(
            "LongTermDebtNoncurrent", "LongTermDebt"
        )
        # Shares for market cap: use the robust, staleness-guarded selector (dei
        # cover-page count first). This fixes the bug where a years-stale us-gaap
        # share count was paired with current financials → a 1000x-wrong market cap.
        shares = self._shares_outstanding_as_of(payload, as_of)
        # Prior-year shares (only feeds the F-Score dilution signal): best-effort
        # annual us-gaap count, or None when unavailable (signal then scores as
        # non-evaluable rather than wrong).
        _, prior_shares = pair("CommonStockSharesOutstanding", "CommonStockSharesIssued")

        rev_series = self._annual_revenue_as_of(payload, as_of)
        revenue = float(rev_series[-1]) if len(rev_series) >= 1 else None
        prior_revenue = float(rev_series[-2]) if len(rev_series) >= 2 else None

        return {
            "common_equity": equity,
            "net_income": net_income,
            "operating_cf": operating_cf,
            "revenue": revenue,
            "total_assets": assets,
            "gross_profit": gross_profit,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "long_term_debt": long_term_debt,
            "shares_outstanding": shares,
            "prior_net_income": prior_net_income,
            "prior_total_assets": prior_assets,
            "prior_operating_cf": prior_operating_cf,
            "prior_revenue": prior_revenue,
            "prior_gross_profit": prior_gross_profit,
            "prior_current_assets": prior_current_assets,
            "prior_current_liabilities": prior_current_liabilities,
            "prior_long_term_debt": prior_long_term_debt,
            "prior_shares_outstanding": prior_shares,
        }

    def quality_metrics_as_of(
        self, ticker: str, as_of: date, payload: dict[str, Any] | None = None
    ) -> dict[str, float | None]:
        """
        Point-in-time quality inputs for the screening quality gate, using only
        EDGAR filings filed on or before `as_of`. Returns floats (the screening
        engine and backtest runner work in floats):
        - fcf_ttm:        operating cash flow - capex (latest annual)
        - debt_to_equity: total liabilities / stockholders equity
        - gross_profit:   GrossProfit (or Revenue - CostOfRevenue)
        - total_assets:   Assets
        - gp_to_assets:   gross_profit / total_assets (Novy-Marx gross profitability)
        """
        payload = payload if payload is not None else self.fetch_company_facts(ticker)
        operating_cf = self._latest_as_of(payload, "NetCashProvidedByUsedInOperatingActivities", as_of)
        capex = self._latest_as_of(payload, "PaymentsToAcquirePropertyPlantAndEquipment", as_of)
        liabilities = self._latest_as_of(payload, "Liabilities", as_of)
        equity = self._latest_as_of(payload, "StockholdersEquity", as_of)
        assets = self._latest_as_of(payload, "Assets", as_of)
        gross_profit = self._gross_profit_as_of(payload, as_of)

        fcf = None
        if operating_cf is not None and capex is not None:
            fcf = self._decimal(operating_cf) - self._decimal(capex)
        debt_to_equity = None
        if liabilities is not None and equity is not None and self._decimal(equity) != 0:
            debt_to_equity = self._decimal(liabilities) / self._decimal(equity)
        total_assets = self._decimal(assets) if assets is not None else None
        gp_to_assets = None
        if gross_profit is not None and total_assets not in (None, Decimal("0")):
            gp_to_assets = float(gross_profit / total_assets)

        # Year-over-year total-asset growth (George-Hwang-Lin q-theory / Hou-Xue-
        # Zhang): the 52w-high premium concentrates in LOW asset-growth firms.
        annual_assets = self._annual_assets_as_of(payload, as_of)
        asset_growth = None
        if len(annual_assets) >= 2 and annual_assets[-2] != Decimal("0"):
            asset_growth = float(annual_assets[-1] / annual_assets[-2] - 1)

        return {
            "fcf_ttm": float(fcf) if fcf is not None else None,
            "debt_to_equity": float(debt_to_equity) if debt_to_equity is not None else None,
            "gross_profit": float(gross_profit) if gross_profit is not None else None,
            "total_assets": float(total_assets) if total_assets is not None else None,
            "gp_to_assets": gp_to_assets,
            "asset_growth": asset_growth,
        }
