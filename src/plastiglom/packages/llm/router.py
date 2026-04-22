"""Task -> model routing. See §8 of DESIGN.md.

The router enforces which model is allowed to service which task so that
callers can't silently pick the wrong one. Prompt-caching is applied on the
shared-context blocks marked `cacheable_system`.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from plastiglom.packages.llm.types import LLMCall, LLMResponse

logger = logging.getLogger(__name__)


class Task(StrEnum):
    TAG_ASSIGNMENT = "tag_assignment"
    DAILY_INDEX_SUMMARY = "daily_index_summary"
    PROMPT_CLEANUP = "prompt_cleanup"
    WEEKLY_ANALYSIS = "weekly_analysis"
    MONTHLY_ANALYSIS = "monthly_analysis"
    ADHOC_QUERY = "adhoc_query"
    MEMORY_UPDATE = "memory_update"
    EXERCISE_EDIT = "exercise_edit"
    BLIND_SPOT_DETECTION = "blind_spot_detection"


_SONNET_TASKS = {
    Task.TAG_ASSIGNMENT,
    Task.DAILY_INDEX_SUMMARY,
    Task.PROMPT_CLEANUP,
}
_OPUS_TASKS = {
    Task.WEEKLY_ANALYSIS,
    Task.MONTHLY_ANALYSIS,
    Task.ADHOC_QUERY,
    Task.MEMORY_UPDATE,
    Task.EXERCISE_EDIT,
    Task.BLIND_SPOT_DETECTION,
}


@dataclass
class LLMRouter:
    sonnet_model: str
    opus_model: str
    api_key: str | None = None
    usage_log_path: Path | None = None

    def model_for(self, task: Task) -> str:
        if task in _SONNET_TASKS:
            return self.sonnet_model
        if task in _OPUS_TASKS:
            return self.opus_model
        raise ValueError(f"unrouted task: {task!r}")

    def invoke(self, task: Task, call: LLMCall) -> LLMResponse:
        """Dispatch a call to the Anthropic API and log usage.

        Import is lazy so the package remains usable without the `anthropic`
        SDK installed for unit tests that don't hit the API.
        """
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")

        from anthropic import Anthropic

        client = Anthropic(api_key=self.api_key)
        model = self.model_for(task)
        system_blocks = _build_system_blocks(call)

        started = time.monotonic()
        create_kwargs: dict[str, object] = {
            "model": model,
            "max_tokens": call.max_tokens,
            "system": system_blocks,
            "messages": [{"role": "user", "content": call.user}],
        }
        if call.temperature is not None:
            create_kwargs["temperature"] = call.temperature
        message = client.messages.create(**create_kwargs)
        elapsed_ms = int((time.monotonic() - started) * 1000)

        text = "".join(
            block.text for block in message.content if getattr(block, "type", "") == "text"
        )
        usage = getattr(message, "usage", None)
        response = LLMResponse(
            text=text,
            model=model,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            latency_ms=elapsed_ms,
        )
        self._log_usage(task, response)
        return response

    def _log_usage(self, task: Task, resp: LLMResponse) -> None:
        record = {
            "task": task.value,
            "model": resp.model,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "cache_read_tokens": resp.cache_read_tokens,
            "cache_creation_tokens": resp.cache_creation_tokens,
            "latency_ms": resp.latency_ms,
        }
        logger.info("llm.usage %s", record)
        if self.usage_log_path is None:
            return
        self.usage_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.usage_log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")


def _build_system_blocks(call: LLMCall) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    for text in call.cacheable_system:
        if not text:
            continue
        blocks.append(
            {
                "type": "text",
                "text": text,
                "cache_control": {"type": "ephemeral"},
            }
        )
    if call.system:
        blocks.append({"type": "text", "text": call.system})
    return blocks
