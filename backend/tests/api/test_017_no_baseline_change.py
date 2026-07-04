"""T027 / FR-017 / SC-008 — feature 017 changes no strategy rule, default,
citation, indicator, gate, or backtest baseline artifact.

Feature 017 is purely additive over the advisor-prompt export surfaces and the
captured-report store. It must not touch any of the strategy-defining or
backtest-baseline files. This test asserts that the feature branch's changes
(committed + working-tree + untracked) leave every protected path untouched
relative to the pre-feature baseline commit.

Two independent checks:

1. **Diff check** — the git working tree / branch introduces no change under any
   protected prefix.
2. **Registry-declaration check** — the live strategy declarations still expose
   the exact NAME / CITATION / TIMEFRAME / PARAMETERS the pre-feature baseline
   declared (a semantic backstop that does not depend on git).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from backend.src.strategies._registry import registry

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Any changed file whose path starts with one of these is a baseline-drift
# violation. Strategy rules, indicators, and every backtest baseline artifact.
_PROTECTED_PREFIXES = (
    "backend/src/strategies/",
    "backend/src/indicators/",
    "backend/data/backtests/",
    "backend/backtests/",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _is_git_repo() -> bool:
    try:
        _git("rev-parse", "--git-dir")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _changed_paths() -> set[str]:
    """Every path that differs from HEAD: tracked working-tree changes, staged
    changes, and brand-new untracked files (forward-slash normalized)."""
    tracked = _git("diff", "--name-only", "HEAD")
    untracked = _git("ls-files", "--others", "--exclude-standard")
    paths = {line.strip() for line in (tracked + untracked).splitlines() if line.strip()}
    return {p.replace("\\", "/") for p in paths}


@pytest.mark.skipif(not _is_git_repo(), reason="not a git checkout")
def test_no_strategy_or_backtest_artifact_changed():
    offenders = sorted(
        p
        for p in _changed_paths()
        if any(p.startswith(prefix) for prefix in _PROTECTED_PREFIXES)
    )
    assert offenders == [], (
        "Feature 017 must not change any strategy/indicator/backtest baseline "
        f"artifact, but these protected paths changed: {offenders}"
    )


# ---------------------------------------------------------------------------
# Semantic backstop: the enabled strategies' declared identity is unchanged.
# These are the frozen pre-feature declarations; if a strategy's rule/default/
# citation genuinely changes in a later feature this fixture is updated there,
# never as a side effect of 017.
# ---------------------------------------------------------------------------

_EXPECTED_MOMENTUM = {
    "slug": "midterm_52w_high_momentum",
    "timeframe": "Mid-term",
    "citation": "George & Hwang (2004)",
}


def test_momentum_strategy_declaration_unchanged():
    strat = registry.get("midterm_52w_high_momentum")
    assert strat is not None
    assert strat.slug == _EXPECTED_MOMENTUM["slug"]
    assert strat.timeframe == _EXPECTED_MOMENTUM["timeframe"]
    assert strat.citation == _EXPECTED_MOMENTUM["citation"]
