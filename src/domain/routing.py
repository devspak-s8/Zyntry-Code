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


def select_model(
    kind: str,
    risk: str,
    available_providers: set[str],
    provider_order: list[str] | None = None,
    preferred_provider: str | None = None,
    catalog: list[ModelSpec] | None = None,
    stats: dict[str, dict] | None = None,
) -> tuple[ModelSpec | None, list[ModelSpec], dict]:
    """Return ``(selected, candidates, reasoning)`` for a single stage.

    ``stats`` is the evidence layer: {model_id: routing_stats row}. Models with
    a poor success record get an effective-cost penalty so that routing improves
    over time instead of relying purely on static pricing.
    """
    catalog = catalog or MODELS
    provider_order = provider_order or []
    stats = stats or {}

    min_tier = required_tier(kind, risk)
    caps = required_capabilities(kind)

    def provider_rank(m: ModelSpec) -> int:
        if m.provider in provider_order:
            return provider_order.index(m.provider)
        return len(provider_order) + 1

    def failure_penalty(m: ModelSpec) -> float:
        s = stats.get(m.id)
        if not s or not s.get("attempts"):
            return 0.0
        return (s.get("failures", 0) / s["attempts"]) * 2.0  # up to 2x cost

    def effective_cost(m: ModelSpec) -> float:
        return (m.cost_in + m.cost_out) * (1.0 + failure_penalty(m))

    needed = {str(c) for c in caps}

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
    reasoning = {
        "min_tier": min_tier,
        "required_capabilities": sorted(c.value for c in caps),
        "available_providers": sorted(available_providers),
        "candidate_count": len(candidates),
        "evidence_adjusted": bool(stats),
    }
    return selected, candidates, reasoning