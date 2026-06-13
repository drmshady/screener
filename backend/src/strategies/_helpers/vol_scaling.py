import pandas as pd
import numpy as np

def calculate_volatility_scalar(returns: pd.Series, target_vol: float = 0.12, window: int = 126) -> float:
    """
    Barroso-Santa-Clara volatility-scaling helper.
    Calculates a scalar to apply to a position to target a specific annualized volatility,
    based on trailing realized volatility over `window` days.
    """
    if len(returns) < window:
        return 1.0
        
    recent_returns = returns.tail(window)
    realized_vol = recent_returns.std() * np.sqrt(252)
    
    if realized_vol == 0 or pd.isna(realized_vol):
        return 1.0
        
    scalar = target_vol / realized_vol
    # Cap leverage at 2.0
    return min(scalar, 2.0)
