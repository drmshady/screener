from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class BasePattern:
    detected: bool
    base_type: str
    pivot: float | None = None
    handle_high: float | None = None
    base_start: pd.Timestamp | None = None
    base_end: pd.Timestamp | None = None
    base_length_weeks: float | None = None
    base_depth: float | None = None
    confidence: float = 0.0


def _clean(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.DataFrame:
    frame = pd.DataFrame({"high": high, "low": low, "close": close}).dropna()
    if not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(frame.index)
    return frame.sort_index()


def _pattern(
    frame: pd.DataFrame,
    base_type: str,
    *,
    pivot: float,
    handle_high: float | None = None,
    confidence: float,
) -> BasePattern:
    high = float(frame["high"].max())
    low = float(frame["low"].min())
    start = frame.index[0]
    end = frame.index[-1]
    return BasePattern(
        detected=True,
        base_type=base_type,
        pivot=float(pivot),
        handle_high=float(handle_high) if handle_high is not None else None,
        base_start=start,
        base_end=end,
        base_length_weeks=round(len(frame) / 5.0, 3),
        base_depth=(high - low) / high if high > 0 else None,
        confidence=confidence,
    )


def _none() -> BasePattern:
    return BasePattern(detected=False, base_type="none")


def _local_minima(values: list[float]) -> list[int]:
    return [
        idx
        for idx in range(1, len(values) - 1)
        if values[idx] <= values[idx - 1] and values[idx] <= values[idx + 1]
    ]


def _try_double_bottom(frame: pd.DataFrame, max_depth: float) -> BasePattern | None:
    if len(frame) < 14:
        return None
    close = frame["close"].astype(float).tolist()
    minima = _local_minima(close)
    for left_pos, first in enumerate(minima):
        for second in minima[left_pos + 1 :]:
            if second - first < 4:
                continue
            first_low = close[first]
            second_low = close[second]
            if first_low <= 0 or abs(second_low - first_low) / first_low > 0.08:
                continue
            peak_idx = first + max(
                range(1, second - first), key=lambda offset: close[first + offset]
            )
            base = frame.iloc[: min(len(frame), second + 5)]
            high = float(base["high"].max())
            low = float(base["low"].min())
            if high <= 0 or (high - low) / high > max_depth:
                continue
            pivot = float(frame["high"].iloc[peak_idx])
            return _pattern(base, "double_bottom", pivot=pivot, confidence=0.82)
    return None


def _try_cup_with_handle(frame: pd.DataFrame, max_depth: float) -> BasePattern | None:
    if len(frame) < 18:
        return None
    search = frame.iloc[:-3]
    if len(search) < 15:
        return None
    close = search["close"].astype(float).reset_index(drop=True)
    trough_idx = int(close.idxmin())
    if trough_idx < 3 or trough_idx > int(len(search) * 0.7):
        return None
    left_high = float(search["high"].iloc[: trough_idx + 1].max())
    recovery_high = float(search["high"].iloc[trough_idx + 1 :].max())
    if left_high <= 0 or recovery_high < left_high * 0.93:
        return None
    base_high = float(search["high"].max())
    base_low = float(search["low"].min())
    depth = (base_high - base_low) / base_high if base_high > 0 else 1.0
    if depth > max_depth:
        return None
    handle = search.tail(5)
    handle_low = float(handle["low"].min())
    handle_high = float(handle["high"].max())
    handle_close = handle["close"].astype(float)
    if handle_high <= 0 or (handle_high - handle_low) / handle_high > 0.12:
        return None
    if handle_close.min() > handle_close.iloc[0] * 0.99 or handle_close.iloc[-1] > handle_close.iloc[0] * 1.01:
        return None
    if handle_low < base_low + (base_high - base_low) * 0.45:
        return None
    return _pattern(frame, "cup_with_handle", pivot=handle_high, handle_high=handle_high, confidence=0.84)


def _try_cup(frame: pd.DataFrame, max_depth: float) -> BasePattern | None:
    if len(frame) < 35:
        return None
    close = frame["close"].astype(float).reset_index(drop=True)
    trough_idx = int(close.idxmin())
    if trough_idx < 5 or trough_idx > len(frame) - 6:
        return None
    left_high = float(frame["high"].iloc[: trough_idx + 1].max())
    right_high = float(frame["high"].iloc[trough_idx:].max())
    base_high = float(frame["high"].max())
    base_low = float(frame["low"].min())
    depth = (base_high - base_low) / base_high if base_high > 0 else 1.0
    if depth > max_depth or left_high <= 0 or right_high < left_high * 0.93:
        return None
    return _pattern(frame, "cup", pivot=max(left_high, right_high), confidence=0.78)


def _try_flat(frame: pd.DataFrame, max_depth: float) -> BasePattern | None:
    min_len = 25
    if len(frame) < min_len:
        return None
    for window_len in range(min(65, len(frame)), min_len - 1, -1):
        window = frame.tail(window_len)
        high = float(window["high"].max())
        low = float(window["low"].min())
        if high <= 0:
            continue
        depth = (high - low) / high
        start_close = float(window["close"].iloc[0])
        end_close = float(window["close"].iloc[-1])
        drift = abs(end_close - start_close) / start_close if start_close else 1.0
        if depth <= max_depth and drift <= max(0.12, max_depth / 2):
            return _pattern(window, "flat", pivot=high, confidence=0.76)
    return None


def classify_base(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    flat_min_weeks: float = 5.0,
    cup_min_weeks: float = 7.0,
    max_depth: float = 0.33,
    confidence_cutoff: float = 0.7,
) -> BasePattern:
    frame = _clean(high, low, close)
    min_days = 14
    if len(frame) < min_days:
        return _none()

    candidates = [
        _try_double_bottom(frame.tail(90), max_depth),
        _try_cup_with_handle(frame.tail(90), max_depth),
        _try_cup(frame.tail(120), max_depth),
        _try_flat(frame.tail(90), max_depth),
    ]
    candidates = [
        candidate
        for candidate in candidates
        if candidate is not None and candidate.confidence >= confidence_cutoff
    ]
    if not candidates:
        return _none()
    return max(candidates, key=lambda candidate: (candidate.base_end or date.min, candidate.confidence))
