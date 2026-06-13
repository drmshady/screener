from backend.src.data.shariah_etf import parse_holdings_csv

SAMPLE = (
    "Date,Account,StockTicker,CUSIP,SecurityName,Shares,Price,MarketValue,Weightings\n"
    "06/09/2026,SPWO,AAPL,037833100,APPLE INC,100,200,20000,5.0\n"
    "06/09/2026,SPWO,BABA,01609W102,ALIBABA ADR,50,80,4000,1.0\n"
    "06/09/2026,SPWO,-,,Cash&Other,0,0,0,0\n"
    "06/09/2026,SPWO,CASH,,US DOLLAR,0,0,0,0\n"
)


def test_parse_holdings_extracts_tickers_and_skips_cash():
    rows = parse_holdings_csv(SAMPLE, "spwo_holdings", "http://x")
    tickers = [r["ticker"] for r in rows]
    assert tickers == ["AAPL", "BABA"]  # cash / "-" rows skipped
    assert all(r["source_name"] == "spwo_holdings" for r in rows)
    assert all(r["source_kind"] == "external" for r in rows)
    assert rows[0]["source_as_of"] == "06/09/2026"
    assert rows[0]["source_url"] == "http://x"


def test_parse_holdings_empty_returns_no_rows():
    assert parse_holdings_csv("Date,StockTicker\n", "spwo_holdings", "http://x") == []
