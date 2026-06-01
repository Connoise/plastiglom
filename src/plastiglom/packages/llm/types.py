"""Shared LLM call / response types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMCall:
    system: str
    user: str
    # Content blocks that Anthropic should mark as cacheable.
    cacheable_system: list[str] = field(default_factory=list)
    max_tokens: int = 4096
    temperature: float | None = None
    # Adaptive thinking effort ("low" | "medium" | "high" | "max"): when set,
    # passes adaptive thinking + output_config.effort instead of temperature.
    # Required for claude-opus-4-7+ (temperature and budget_tokens are removed).
    thinking_effort: str | None = None


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    latency_ms: int = 0
