"""Stage-specific model routing.

Chooses a model per stage based on:
- the stage's kind (what capabilities it needs),
- the overall task risk (how strong a model is warranted),
- which providers are actually configured,
- cost (cheapest model that meets the requirements wins).
"""

from domain.catalog import ModelSpec, MODELS
from domain.enums import Capability, RiskLevel, StageKind


STAGE_MIN_TIER: dict[StageKind, int] = {
    StageKind.UNDERSTAND: 2,
    StageKind.ANALYZE: 2,
    StageKind.PLAN: 3,
    StageKind.IMPLEMENT: 2,
    StageKind.IMPLEMENT_BACKEND: 2,
    StageKind.IMPLEMENT_FRONTEND: 2,
    StageKind.DATABASE: 3,
    StageKind.TEST: 2,
    StageKind.REVIEW: 3,
    StageKind.SECURITY_REVIEW: 4,
    StageKind.VERIFY: 2,
    StageKind.INTEGRATE: 3,
    StageKind.DOCUMENT: 1,
}

STAGE_CAPABILITIES: dict[StageKind, set[Capability]] = {
    StageKind.UNDERSTAND: {Capability.REASON, Capability.LONG_CONTEXT},
    StageKind.ANALYZE: {Capability.REASON},
    StageKind.PLAN: {Capability.PLAN, Capability.REASON},
    StageKind.IMPLEMENT: {Capability.CODE},
    StageKind.IMPLEMENT_BACKEND: {Capability.CODE},
    StageKind.IMPLEMENT_FRONTEND: {Capability.CODE},
    StageKind.DATABASE: {Capability.CODE, Capability.REASON},
    StageKind.TEST: {Capability.CODE},
    StageKind.REVIEW: {Capability.REVIEW, Capability.REASON},
    StageKind.SECURITY_REVIEW: {Capability.SECURITY, Capability.REVIEW, Capability.REASON},
    StageKind.VERIFY: {Capability.REASON},
    StageKind.INTEGRATE: {Capability.CODE, Capability.REASON},
    StageKind.DOCUMENT: {Capability.CODE},
}

RISK_MIN_TIER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}


def _coerce(value, enum_cls):
    return value if isinstance(value, enum_cls) else enum_cls(value)


def required_tier(kind: str, risk: str) -> int:
    kind = _coerce(kind, StageKind)
    risk = _coerce(risk, RiskLevel)
    return max(STAGE_MIN_TIER.get(kind, 1), RISK_MIN_TIER.get(risk, 1))


def required_capabilities(kind: str) -> set[Capability]:
    kind = _coerce(kind, StageKind)
    return STAGE_CAPABILITIES.get(kind, {Capability.CODE})


# Bayesian shrinkage: a stage-specific record is trusted more as it accumulates
# attempts, but never fully overrides the model's global prior. This turns the
# evidence layer into a *task-specific reliability estimate* instead of one
# global success score.
PRIOR_STRENGTH = 4.0
DEFAULT_RELIABILITY = 0.6
MIN_RELIABILITY = 0.1


def _reliability(row: dict | None, global_row: dict | None) -> tuple[float, str]:
    """Reliability estimate for (model, stage kind, risk), shrunk toward the
    model's global success rate. Returns ``(estimate, evidence_scope)``."""
    global_attempts = int((global_row or {}).get("attempts") or 0)
    global_rate = (
        float(global_row.get("successes") or 0) / global_attempts
        if global_attempts > 0
        else DEFAULT_RELIABILITY
    )
    attempts = int((row or {}).get("attempts") or 0)
    if attempts == 0:
        return global_rate, "global"
    successes = float((row or {}).get("successes") or 0)
    estimate = (successes + PRIOR_STRENGTH * global_rate) / (attempts + PRIOR_STRENGTH)
    return estimate, "stage+risk"


def select_model(
    kind: str,
    risk: str,
    available_providers: set[str],
    provider_order: list[str] | None = None,
    preferred_provider: str | None = None,
    catalog: list[ModelSpec] | None = None,
    stats: dict[str, dict] | None = None,
    global_stats: dict[str, dict] | None = None,
    tier_override: int | None = None,
    preferred_model: str | None = None,
) -> tuple[ModelSpec | None, list[ModelSpec], dict]:
    """Return ``(selected, candidates, reasoning)`` for a single stage.

    ``stats`` is the evidence layer for this exact (stage kind, risk) pair.
    ``global_stats`` is the model's record across all stage kinds and is used
    only as a Bayesian prior when the task-specific record is thin. The routing
    cost is divided by the reliability estimate, so a model that historically
    fails this kind of stage has a higher expected cost than its sticker price.

    ``tier_override`` forces the minimum tier regardless of kind/risk:
    - ``1``  → allow the fastest models that still have the required capabilities
    - ``>=4`` → require reasoning-tier models (quality mode / deep reasoning)

    ``preferred_model`` pins the model exactly (the dashboard's free-model
    picker sets it via task constraints). When the pinned model is unavailable
    (not in the catalog or its provider is not configured), normal routing
    applies so a task never hard-fails on a stale selection.
    """
    catalog = catalog or MODELS
    provider_order = provider_order or []
    stats = stats or {}
    global_stats = global_stats or {}

    min_tier = tier_override if tier_override is not None else required_tier(kind, risk)
    caps = required_capabilities(kind)

    def provider_rank(m: ModelSpec) -> int:
        if m.provider in provider_order:
            return provider_order.index(m.provider)
        return len(provider_order) + 1

    def reliability(m: ModelSpec) -> tuple[float, str]:
        return _reliability(stats.get(m.id), global_stats.get(m.id))

    def effective_cost(m: ModelSpec) -> float:
        estimate, _ = reliability(m)
        return (m.cost_in + m.cost_out) / max(estimate, MIN_RELIABILITY)

    needed = {str(c) for c in caps}

    # Exact pin (model picker): return the requested model when its provider is
    # actually available — regardless of tier/capability filters. Otherwise
    # fall through to normal routing.
    if preferred_model:
        exact = [
            m for m in catalog
            if m.id == preferred_model and m.provider in available_providers
        ]
        if exact:
            reasoning = {
                "min_tier": min_tier,
                "required_capabilities": sorted(c.value for c in caps),
                "available_providers": sorted(available_providers),
                "candidate_count": 1,
                "evidence_adjusted": bool(stats or global_stats),
                "preferred_model": preferred_model,
                "pinned": True,
            }
            return exact[0], exact, reasoning

    candidates = [
        m for m in catalog
        if m.provider in available_providers
        and m.tier >= min_tier
        and needed <= {str(c) for c in m.capabilities}
        and (preferred_provider is None or m.provider == preferred_provider)
    ]

    # Cheapest effective cost first, then provider preference, then lower tier (faster).
    candidates.sort(key=lambda m: (effective_cost(m), provider_rank(m), m.tier))

    selected = candidates[0] if candidates else None
    selected_reliability, evidence_scope = (
        reliability(selected) if selected is not None else (None, None)
    )
    reasoning = {
        "min_tier": min_tier,
        "required_capabilities": sorted(c.value for c in caps),
        "available_providers": sorted(available_providers),
        "candidate_count": len(candidates),
        "evidence_adjusted": bool(stats or global_stats),
        "reliability_scope": evidence_scope,
        "selected_reliability": (
            round(selected_reliability, 4) if selected_reliability is not None else None
        ),
    }
    return selected, candidates, reasoning