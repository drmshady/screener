import os
import glob
import pandas as pd
from datetime import date, datetime, timezone
from typing import List, Optional

from .prices import PriceProvider

STOOQ_DIR = "backend/data/prices/stooq"

class StooqHistoricalProvider(PriceProvider):
    def fetch_ohlcv(self, tickers: List[str], start_date: Optional[date] = None, end_date: Optional[date] = None) -> pd.DataFrame:
        """
        Reads from downloaded Stooq CSV bundles.
        Expects CSVs in STOOQ_DIR, either zipped or extracted, with name matching <ticker>.us.txt
        """
        records = []
        now = datetime.now(timezone.utc)
        
        for ticker in tickers:
            # Stooq files are typically named like "aapl.us.txt"
            pattern = os.path.join(STOOQ_DIR, "**", f"{ticker.lower()}.us.txt")
            matches = glob.glob(pattern, recursive=True)
            
            if not matches:
                continue
                
            filepath = matches[0]
            try:
                # Stooq format: <TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>
                # or: <TICKER>,<DATE>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>
                df = pd.read_csv(filepath)
                # Ensure column names are standard
                df.columns = [c.lower().strip() for c in df.columns]
                
                # Filter by date
                df['date'] = pd.to_datetime(df['date']).dt.date
                if start_date:
                    df = df[df['date'] >= start_date]
                if end_date:
                    df = df[df['date'] <= end_date]
                    
                for _, row in df.iterrows():
                    # Stooq provides adjusted or unadjusted depending on the bundle.
                    # We assume it's unadjusted, but sometimes Stooq only provides adjusted.
                    # We will map both close and adj_close to the same for now, or use standard logic.
                    close_val = float(row['close'])
                    records.append({
                        "ticker": ticker.upper(),
                        "as_of_date": row['date'],
                        "open": float(row['open']),
                        "high": float(row['high']),
                        "low": float(row['low']),
                        "close": close_val,
                        "adj_close": close_val, # Default to close if not provided separately
                        "volume": int(row['vol']),
                        "source_name": "stooq",
                        "source_as_of": now
                    })
            except Exception as e:
                print(f"Failed to read Stooq data for {ticker}: {e}")
                
        return pd.DataFrame(records)
