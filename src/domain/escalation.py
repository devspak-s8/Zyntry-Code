"""Verification-triggered escalation and cost/latency estimation."""

from domain.catalog import ModelSpec, MODELS


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def attempt_cost(model: ModelSpec, tokens_in: int, tokens_out: int) -> float:
    return (tokens_in / 1_000_000) * model.cost_in + (tokens_out / 1_000_000) * model.cost_out


def escalation_candidates(
    current: ModelSpec,
    required_caps: set[str],
    available_providers: set[str],
    catalog: list[ModelSpec] | None = None,
) -> list[ModelSpec]:
    """Stronger models (higher tier) eligible to take over a failed attempt."""
    catalog = catalog or MODELS
    needed = {str(c) for c in required_caps}
    stronger = [
        m for m in catalog
        if m.provider in available_providers
        and m.tier > current.tier
        and needed <= {str(c) for c in m.capabilities}
    ]
    stronger.sort(key=lambda m: (m.cost_in + m.cost_out, m.tier))
    return stronger


def fallback_candidates(
    current: ModelSpec,
    required_caps: set[str],
    available_providers: set[str],
    catalog: list[ModelSpec] | None = None,
) -> list[ModelSpec]:
    """Same-tier models on a DIFFERENT provider (for outage fallback)."""
    catalog = catalog or MODELS
    needed = {str(c) for c in required_caps}
    same_tier = [
        m for m in catalog
        if m.provider in available_providers
        and m.provider != current.provider
        and m.tier >= current.tier
        and needed <= {str(c) for c in m.capabilities}
    ]
    same_tier.sort(key=lambda m: (m.cost_in + m.cost_out, m.tier))
    return same_tier


def next_model(
    current: ModelSpec,
    required_caps: set[str],
    available_providers: set[str],
    catalog: list[ModelSpec] | None = None,
) -> tuple[ModelSpec, bool]:
    """Pick the model for the next attempt: a stronger one if available,
    otherwise a retry with the same model carrying the failure context."""
    stronger = escalation_candidates(current, required_caps, available_providers, catalog)
    if stronger:
        return stronger[0], True
    return current, False


def build_failure_context(
    failure_reasons: list[str],
    prior_output: str | None = None,
) -> str:
    """Failure evidence to append to the NEXT attempt's prompt."""
    reasons = "\n".join(f"- {r}" for r in failure_reasons) or "- (unknown failure)"
    prior = (prior_output or "").strip()
    prior_block = f"\n\nPrevious attempt output:\n```\n{prior[:3000]}\n```" if prior else ""
    return (
        f"# Previous attempt did not pass verification\n"
        f"Verification failures:\n{reasons}\n"
        f"Correct these issues and produce a complete, correct result."
        f"{prior_block}"
    )


def build_escalation_prompt(
    original_prompt: str,
    failure_reasons: list[str],
    prior_output: str | None,
) -> str:
    return f"{original_prompt}\n\n{build_failure_context(failure_reasons, prior_output)}"