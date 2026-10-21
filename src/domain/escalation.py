"""Verification-triggered escalation and cost/latency estimation."""

from domain.catalog import ModelSpec, MODELS


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def attempt_cost(model: ModelSpec, tokens_in: int, tokens_out: int) -> float:
    return (tokens_in / 1_000_000) * model.cost_in + (tokens_out / 1_000_000) * model.cost_out


# ---- full stage projection (budget guard) -----------------------------------
# The budget guard must reserve the *entire* projected retry cost, not just the
# first attempt: failure context grows the input on every retry, verification
# consumes tokens of its own, and an escalation may switch to a pricier model.
RETRY_CONTEXT_GROWTH = 0.35          # +35% input per retry (previous output + failures)
RETRY_CONTEXT_FIXED_TOKENS = 600     # fixed failure-context overhead per retry
VERIFICATION_INPUT_TOKENS = 900      # reserved for semantic verification
VERIFICATION_OUTPUT_TOKENS = 300
DEFAULT_OUTPUT_TOKENS = 4096

#: Labels recorded on budget events so the UI can explain what was included.
PROJECTION_INCLUDES = ("input_context", "model_output", "retries", "verification")


def verification_cost(model: ModelSpec) -> float:
    """Reserved cost for verification operations on one attempt."""
    return attempt_cost(model, VERIFICATION_INPUT_TOKENS, VERIFICATION_OUTPUT_TOKENS)


def projected_stage_cost(
    model: ModelSpec,
    tokens_in: int,
    remaining_attempts: int,
    next_model=None,
    output_tokens: int = DEFAULT_OUTPUT_TOKENS,
) -> float:
    """Worst-case cost of finishing a stage from here.

    Includes every remaining attempt, the growing input context on retries, the
    verification allowance per attempt, and escalation to whichever model
    ``next_model`` returns. Runner commands have no token price, so they add no
    monetary cost; their verification allowance is still reserved.
    """
    total = 0.0
    current = model
    attempts = max(1, int(remaining_attempts))
    for attempt in range(attempts):
        growth = 1.0 + RETRY_CONTEXT_GROWTH * attempt
        input_est = int(tokens_in * growth) + RETRY_CONTEXT_FIXED_TOKENS * attempt
        total += attempt_cost(current, input_est, output_tokens)
        total += verification_cost(current)
        if next_model is not None and attempt < attempts - 1:
            current = next_model(current)
    return total


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