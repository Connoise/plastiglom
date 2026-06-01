import pytest

from plastiglom.packages.llm.router import LLMRouter, Task
from plastiglom.packages.llm.types import LLMCall


class _FakeMessage:
    content: list = []
    usage = None


class _FakeClient:
    """Records the kwargs passed to messages.create."""

    last_kwargs: dict = {}

    def __init__(self, *_args, **_kwargs):
        pass

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        _FakeClient.last_kwargs = kwargs
        return _FakeMessage()


@pytest.fixture
def fake_anthropic(monkeypatch):
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)
    _FakeClient.last_kwargs = {}
    return _FakeClient


def test_model_routing():
    router = LLMRouter(sonnet_model="claude-sonnet-4-6", opus_model="claude-opus-4-7")
    assert router.model_for(Task.TAG_ASSIGNMENT) == "claude-sonnet-4-6"
    assert router.model_for(Task.WEEKLY_ANALYSIS) == "claude-opus-4-7"
    assert router.model_for(Task.EXERCISE_EDIT) == "claude-opus-4-7"


def test_invoke_without_api_key_raises():
    router = LLMRouter(sonnet_model="s", opus_model="o", api_key=None)

    with pytest.raises(RuntimeError):
        router.invoke(Task.TAG_ASSIGNMENT, LLMCall(system="", user=""))


def test_opus_task_uses_adaptive_thinking_and_effort(fake_anthropic):
    # opus-4-7+ rejects thinking.type=enabled/budget_tokens; the router must
    # emit adaptive thinking + output_config.effort instead.
    router = LLMRouter(
        sonnet_model="claude-sonnet-4-6",
        opus_model="claude-opus-4-8",
        api_key="k",
        thinking_effort="high",
    )
    router.invoke(Task.MONTHLY_ANALYSIS, LLMCall(system="s", user="u", max_tokens=4096))

    kwargs = fake_anthropic.last_kwargs
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {"effort": "high"}
    assert "temperature" not in kwargs
    # Adaptive thinking eats into the output budget; max_tokens gets headroom.
    assert kwargs["max_tokens"] >= 16000


def test_sonnet_task_keeps_temperature_and_no_thinking(fake_anthropic):
    router = LLMRouter(
        sonnet_model="claude-sonnet-4-6",
        opus_model="claude-opus-4-8",
        api_key="k",
        thinking_effort="high",
    )
    router.invoke(
        Task.TAG_ASSIGNMENT, LLMCall(system="s", user="u", temperature=0.2)
    )

    kwargs = fake_anthropic.last_kwargs
    assert "thinking" not in kwargs
    assert "output_config" not in kwargs
    assert kwargs["temperature"] == 0.2
