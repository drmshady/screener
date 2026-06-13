from __future__ import annotations

import json

from backend.src.screening.engine import run_strategy


def _canonical(result):
    return {
        "candidate_count": result.candidate_count,
        "tickers": [candidate.ticker for candidate in result.candidates],
        "scores": [candidate.score for candidate in result.candidates],
        "gates": [
            [(gate.gate, gate.status, gate.detail) for gate in candidate.gate_results]
            for candidate in result.candidates
        ],
        "notes": result.data_notes,
    }


def test_midterm_screen_is_deterministic() -> None:
    payload = {
        "parameters": {"regime_gate": False, "refresh_events": False},
        "filters": {"shariah_only": True, "exclude_earnings_within_days": 0},
        "shariah_overrides": {
            "active_sources": [
                "spus_holdings",
                "spwo_holdings",
                "spre_holdings",
                "spte_holdings",
                "halal_terminal",
            ]
        },
    }
    first = _canonical(run_strategy("midterm_52w_high_momentum", **payload))
    second = _canonical(run_strategy("midterm_52w_high_momentum", **payload))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
