import pandas as pd

def rank_within_sector(df: pd.DataFrame, score_column: str, ascending: bool = False, max_per_sector: int = 5) -> pd.DataFrame:
    """
    Ranks candidates within their sector based on a score column,
    and returns a filtered DataFrame keeping at most `max_per_sector` candidates per sector.
    """
    if df.empty or score_column not in df.columns or 'sector' not in df.columns:
        return df
        
    df['sector_rank'] = df.groupby('sector')[score_column].rank(ascending=ascending, method='first')
    return df[df['sector_rank'] <= max_per_sector].drop(columns=['sector_rank'])
