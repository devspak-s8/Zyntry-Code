"""Model catalog and routing tiers.

This is a static, editable registry of the models Zyntry Code can route to.
Prices are USD per 1M tokens and are ILLUSTRATIVE — replace them with your
provider's current pricing. Only models whose provider is actually configured
(has a key or a Workers AI binding) are eligible at routing time.
"""

from dataclasses import dataclass
from typing import Iterable

from domain.enums import Capability


@dataclass(frozen=True)
class ModelSpec:
    id: str
    provider: str          # "openai" | "anthropic" | "workers_ai"
    display_name: str
    tier: int              # 1 = fast/cheap ... 4 = frontier reasoning
    context_window: int
    cost_in: float         # USD per 1M input tokens
    cost_out: float        # USD per 1M output tokens
    capabilities: frozenset[str]
    latency_class: str = "fast"   # fast | balanced | slow


# NOTE: illustrative. Add/remove models to match what you actually have access to.
MODELS: list[ModelSpec] = [
    # ---- OpenAI / OpenAI-compatible ----
    ModelSpec("gpt-4.1-mini", "openai", "GPT-4.1 mini", 1, 128_000, 0.40, 1.60,
              frozenset({Capability.CODE, Capability.REASON}), "fast"),
    ModelSpec("gpt-4.1", "openai", "GPT-4.1", 2, 1_000_000, 2.00, 8.00,
              frozenset({Capability.CODE, Capability.REASON, Capability.REVIEW, Capability.LONG_CONTEXT}), "balanced"),
    ModelSpec("o3-mini", "openai", "o3-mini", 3, 200_000, 1.10, 4.40,
              frozenset({Capability.CODE, Capability.REASON, Capability.PLAN}), "balanced"),
    ModelSpec("gpt-4o", "openai", "GPT-4o", 3, 128_000, 2.50, 10.00,
              frozenset({Capability.CODE, Capability.REASON, Capability.REVIEW, Capability.VISION}), "balanced"),
    ModelSpec("gpt-5-mini", "openai", "GPT-5 mini", 3, 400_000, 0.25, 2.00,
              frozenset({Capability.CODE, Capability.REASON, Capability.PLAN, Capability.LONG_CONTEXT}), "balanced"),
    ModelSpec("gpt-5", "openai", "GPT-5", 4, 400_000, 1.25, 10.00,
              frozenset({Capability.CODE, Capability.REASON, Capability.PLAN, Capability.REVIEW,
                         Capability.SECURITY, Capability.LONG_CONTEXT}), "slow"),

    # ---- Anthropic ----
    ModelSpec("claude-haiku-4-5", "anthropic", "Claude Haiku 4.5", 1, 200_000, 1.00, 5.00,
              frozenset({Capability.CODE, Capability.REASON}), "fast"),
    ModelSpec("claude-sonnet-4-5", "anthropic", "Claude Sonnet 4.5", 3, 200_000, 3.00, 15.00,
              frozenset({Capability.CODE, Capability.REASON, Capability.REVIEW}), "balanced"),
    ModelSpec("claude-opus-4-5", "anthropic", "Claude Opus 4.5", 4, 200_000, 15.00, 75.00,
              frozenset({Capability.CODE, Capability.REASON, Capability.REVIEW, Capability.SECURITY, Capability.PLAN}), "slow"),

    # ---- Cloudflare Workers AI (edge inference, no API key) ----
    ModelSpec("@cf/meta/llama-3.3-70b-instruct-fp8-fast", "workers_ai", "Llama 3.3 70B (fp8)", 2, 128_000, 0.0, 0.0,
              frozenset({Capability.CODE, Capability.REASON}), "fast"),
    ModelSpec("@cf/deepseek-ai/deepseek-v3-0324", "workers_ai", "DeepSeek V3", 3, 64_000, 0.0, 0.0,
              frozenset({Capability.CODE, Capability.REASON, Capability.PLAN}), "balanced"),
    ModelSpec("@cf/meta/llama-4-scout-17b-16e-instruct", "workers_ai", "Llama 4 Scout 17B", 2, 10_000_000, 0.0, 0.0,
              frozenset({Capability.CODE, Capability.REASON, Capability.LONG_CONTEXT}), "fast"),
]


def get_model(model_id: str) -> ModelSpec | None:
    for m in MODELS:
        if m.id == model_id:
            return m
    return None


def models_for_provider(provider: str) -> list[ModelSpec]:
    return [m for m in MODELS if m.provider == provider]


def models_by_capabilities(caps: Iterable[str], min_tier: int = 1) -> list[ModelSpec]:
    needed = set(caps)
    return [m for m in MODELS if m.tier >= min_tier and needed <= set(m.capabilities)]