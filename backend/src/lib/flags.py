from __future__ import annotations

import os

from . import hosting

# Operator-override flags, following the same env-var convention used inside the
# strategy modules (e.g. SCREENER_TREAT_STRATEGY_VALID, SCREENER_GATE_MODE).

_TRUTHY = {"1", "true", "yes", "on"}


def personal_use_directive() -> bool:
    """Whether the advisor prompt may use directive (take/pass/size) framing.

    DEFAULT OFF. The app's no-advice boundary (constitution Principle V) applies
    by default; this flag enables the personal-use, single-user exception. It may
    only be defaulted on after the Principle V amendment scoping that exception
    (see specs/004-advisor-prompt-export/plan.md, Complexity Tracking).
    Override with SCREENER_PERSONAL_USE_DIRECTIVE=1.
    """
    if hosting.hosted_mode():
        return False
    return os.getenv("SCREENER_PERSONAL_USE_DIRECTIVE", "0").strip().lower() in _TRUTHY
