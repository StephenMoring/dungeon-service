import importlib

import pytest

import src.services.dm_agent as dm_agent_module


@pytest.fixture
def restore_dm_agent():
    """Reload dm_agent after the test to restore the module-level client."""
    yield
    importlib.reload(dm_agent_module)


def test_mock_client_selected_when_mock_llm_set(monkeypatch, restore_dm_agent):
    monkeypatch.setenv("MOCK_LLM", "true")
    importlib.reload(dm_agent_module)

    from src.services.mock_llm import MockAnthropicClient
    assert isinstance(dm_agent_module.client, MockAnthropicClient)


def test_real_client_selected_when_mock_llm_not_set(monkeypatch, restore_dm_agent):
    monkeypatch.delenv("MOCK_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    importlib.reload(dm_agent_module)

    from anthropic import Anthropic
    assert isinstance(dm_agent_module.client, Anthropic)
