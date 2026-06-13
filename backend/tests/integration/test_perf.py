from __future__ import annotations

import statistics
import time

from fastapi.testclient import TestClient

from backend.src.api.app import app
from backend.src.screening import engine
from backend.src.screening.engine import run_strategy
from backend.src import strategies as _strategies  # noqa: F401 - register strategies


def _elapsed_seconds(fn):
    start = time.perf_counter()
    result = fn()
    return time.perf_counter() - start, result


def _p95(samples: list[float]) -> float:
    if len(samples) < 2:
        return samples[0]
    return statistics.quantiles(samples, n=20, method="inclusive")[18]


def test_current_broad_screen_meets_warm_cache_perf_budget():
    # Build the real Stooq-derived disk snapshot first. This mirrors the Phase 10
    # warm-keeper path: a restarted app should read local computed data, not fetch
    # or rebuild the full broad-market snapshot on the first user click.
    run_strategy(
        "midterm_52w_high_momentum",
        parameters={"regime_gate": False, "refresh_events": False},
        filters={"exclude_earnings_within_days": 0},
    )
    engine._STOOQ_SNAPSHOT_CACHE.clear()

    cold_seconds, cold_result = _elapsed_seconds(
        lambda: run_strategy(
            "midterm_52w_high_momentum",
            parameters={"regime_gate": False, "refresh_events": False},
            filters={"exclude_earnings_within_days": 0},
        )
    )
    assert cold_result.candidate_count >= 0
    assert cold_seconds <= 10.0

    warm_samples = []
    for _ in range(5):
        seconds, result = _elapsed_seconds(
            lambda: run_strategy(
                "midterm_52w_high_momentum",
                parameters={"regime_gate": False, "refresh_events": False},
                filters={"exclude_earnings_within_days": 0},
            )
        )
        assert result.id == cold_result.id
        warm_samples.append(seconds)

    assert _p95(warm_samples) <= 2.0


def test_candidate_and_home_dashboard_perf_budgets():
    client = TestClient(app)

    # Prime route-level caches, then measure returning-session behavior.
    assert client.get("/regime").status_code == 200
    assert client.get("/events/market?days_ahead=60").status_code == 200
    assert client.get("/candidates/HFRO").status_code == 200

    candidate_samples = []
    dashboard_samples = []
    for _ in range(5):
        seconds, response = _elapsed_seconds(lambda: client.get("/candidates/HFRO"))
        assert response.status_code == 200
        candidate_samples.append(seconds)

        start = time.perf_counter()
        regime = client.get("/regime")
        events = client.get("/events/market?days_ahead=60")
        dashboard_samples.append(time.perf_counter() - start)
        assert regime.status_code == 200
        assert events.status_code == 200

    assert _p95(candidate_samples) <= 1.5
    assert _p95(dashboard_samples) <= 1.0
