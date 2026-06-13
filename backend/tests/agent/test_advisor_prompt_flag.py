from __future__ import annotations

from backend.src.agent.advisor_prompt import build_advisor_prompt

SURV = {"confirmed": True, "passed": False, "note": "x"}
_BANNED = ("buy", "sell", "recommended", "strong buy")


def test_neutral_prompt_has_no_directive_language(sample_result, midterm_strategy):
    prompt = build_advisor_prompt(
        sample_result, midterm_strategy, survivorship=SURV, regime="Trending up", directive=False
    )
    lower = prompt.lower()
    for word in _BANNED:
        assert word not in lower, f"directive word leaked into neutral prompt: {word!r}"
    assert "candidate for further research" in lower


def test_directive_prompt_uses_directive_framing(sample_result, midterm_strategy):
    prompt = build_advisor_prompt(
        sample_result, midterm_strategy, survivorship=SURV, regime="Trending up", directive=True
    )
    lower = prompt.lower()
    assert "directive" in lower
    assert "take / pass / size" in lower
    # personal-use scope reminder must be present when directive
    assert "must not be redistributed" in lower
