import pytest

from plastiglom.packages.llm.router import LLMRouter, Task


def test_model_routing():
    router = LLMRouter(sonnet_model="claude-sonnet-4-6", opus_model="claude-opus-4-7")
    assert router.model_for(Task.TAG_ASSIGNMENT) == "claude-sonnet-4-6"
    assert router.model_for(Task.WEEKLY_ANALYSIS) == "claude-opus-4-7"
    assert router.model_for(Task.EXERCISE_EDIT) == "claude-opus-4-7"


def test_invoke_without_api_key_raises():
    router = LLMRouter(sonnet_model="s", opus_model="o", api_key=None)
    from plastiglom.packages.llm.types import LLMCall

    with pytest.raises(RuntimeError):
        router.invoke(Task.TAG_ASSIGNMENT, LLMCall(system="", user=""))
