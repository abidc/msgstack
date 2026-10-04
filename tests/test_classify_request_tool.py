"""The classify_request MCP tool (src/server.py) — thin wrapper around decide().

No existing tests/test_server.py convention exists for @mcp.tool() functions (most are
exercised via the grounding_tools layer they delegate to); this one has no grounding_tools
equivalent since it's a direct decide() wrapper, so it gets its own small test file.
"""
import os
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from src.server import classify_request


def test_classify_request_returns_decision_result_shape():
    with patch("src.decision_model.settings.decision_model_url", ""), \
         patch("src.decision_model.llm_client") as mock_llm_client:
        fake_response = mock_llm_client.return_value.chat.completions.create.return_value
        fake_response.choices = [type("M", (), {"message": type("M2", (), {"content": '{"choice": "battlecard", "confidence": 0.8}'})()})()]
        result = classify_request(text="arm me for the call", options=["battlecard", "one_pager"])

    assert result == {"choice": "battlecard", "confidence": 0.8, "source": "llm_fallback"}


def test_classify_request_rejects_choice_outside_fixed_set_by_raising():
    with patch("src.decision_model.settings.decision_model_url", ""), \
         patch("src.decision_model.llm_client") as mock_llm_client:
        fake_response = mock_llm_client.return_value.chat.completions.create.return_value
        fake_response.choices = [type("M", (), {"message": type("M2", (), {"content": "completely unrelated text"})()})()]
        with pytest.raises(ValueError):
            classify_request(text="arm me for the call", options=["battlecard", "one_pager"])


def test_classify_request_passes_context_through():
    with patch("src.decision_model.settings.decision_model_url", ""), \
         patch("src.decision_model.llm_client") as mock_llm_client:
        fake_response = mock_llm_client.return_value.chat.completions.create.return_value
        fake_response.choices = [type("M", (), {"message": type("M2", (), {"content": '{"choice": "a", "confidence": 1.0}'})()})()]
        classify_request(text="pick", options=["a", "b"], context="extra grounding context")

    sent_prompt = mock_llm_client.return_value.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "extra grounding context" in sent_prompt
