"""Strategy-agnostic output-contract type system (feature 008, data-model §1-§3).

A strategy declares an :class:`OutputContract` — an ordered list of
:class:`Invariant`s describing the properties every returned candidate row must
satisfy. A single engine (``integrity/engine.py``) evaluates any contract
unchanged (FR-001), producing :class:`ContractViolation`s per row.

Predicates are pure ``Callable[[row, signals], bool]`` (data-model §2): no I/O,
no wall-clock, ``True`` == satisfied. They read the candidate row plus the
precomputed series-integrity ``signals`` columns (Decision 7) and never
re-fetch.
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# Pure predicate over (candidate_row, signals_row) -> satisfied?
Predicate = Callable[[Any, Any], bool]


class Invariant(BaseModel):
    """One machine-checkable rule a correct candidate row must satisfy.

    `severity="candidate"` -> a breach yields a per-candidate data-integrity
    warning and demotion (FR-017/FR-018). `severity="aggregate"` -> a breach is
    recorded once as a screen-level data note (FR-004).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    family: str  # coherence | gate | score | level | value_domain | series | identity
    severity: str  # "candidate" | "aggregate"
    # Excluded from serialization (a Callable is not JSON-safe), mirroring the
    # existing Strategy.rules pattern; the declarative fields stay inspectable
    # for transparency (Principle II).
    predicate: Predicate = Field(exclude=True)
    figure: Optional[str] = None
    message: str


class OutputContract(BaseModel):
    """A strategy's declarative output contract (data-model §1)."""

    strategy_slug: str
    invariants: List[Invariant] = Field(default_factory=list)


class ContractViolation(BaseModel):
    """A detected breach of an invariant for one candidate row (data-model §3)."""

    invariant_name: str
    family: str
    figure: Optional[str] = None
    reason: str
    severity: str  # "candidate" | "aggregate"
