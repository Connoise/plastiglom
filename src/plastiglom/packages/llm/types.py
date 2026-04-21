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
    temperature: float = 0.2


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    latency_ms: int = 0
