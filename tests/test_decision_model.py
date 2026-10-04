import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from src.decision_model import DecisionResult, decide


def test_trivial_single_option_short_circuits():
    result = decide(options=["only_choice"], prompt="pick one")
    assert result == DecisionResult(choice="only_choice", confidence=1.0, source="trivial")


def test_empty_options_raises():
    with pytest.raises(ValueError):
        decide(options=[], prompt="pick one")


def test_decision_model_endpoint_used_when_configured():
    fake_response = MagicMock()
    fake_response.json.return_value = {"choice": "violation", "confidence": 0.93}
    fake_response.raise_for_status.return_value = None

    with patch("src.decision_model.settings") as mock_settings, \
         patch("src.decision_model.requests.post", return_value=fake_response) as mock_post:
        mock_settings.decision_model_url = "http://localhost:9999"
        result = decide(options=["violation", "not_a_violation"], prompt="is this a violation?")

    assert result == DecisionResult(choice="violation", confidence=0.93, source="decision_model")
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["json"]["options"] == ["violation", "not_a_violation"]


def test_decision_model_endpoint_failure_falls_back_to_llm():
    fake_llm_response = MagicMock()
    fake_llm_response.choices = [MagicMock(message=MagicMock(content='{"choice": "not_a_violation", "confidence": 0.8}'))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_llm_response

    with patch("src.decision_model.settings") as mock_settings, \
         patch("src.decision_model.requests.post", side_effect=ConnectionError("endpoint down")), \
         patch("src.decision_model.llm_client", return_value=fake_client):
        mock_settings.decision_model_url = "http://localhost:9999"
        result = decide(options=["violation", "not_a_violation"], prompt="is this a violation?")

    assert result.choice == "not_a_violation"
    assert result.source == "llm_fallback"


def test_no_endpoint_configured_goes_straight_to_llm_fallback():
    fake_llm_response = MagicMock()
    fake_llm_response.choices = [MagicMock(message=MagicMock(content='{"choice": "b", "confidence": 0.6}'))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_llm_response

    with patch("src.decision_model.settings") as mock_settings, \
         patch("src.decision_model.requests.post") as mock_post, \
         patch("src.decision_model.llm_client", return_value=fake_client):
        mock_settings.decision_model_url = ""
        result = decide(options=["a", "b"], prompt="pick one")

    mock_post.assert_not_called()
    assert result.choice == "b"
    assert result.source == "llm_fallback"


def test_llm_fallback_recovers_from_non_json_plain_text():
    fake_llm_response = MagicMock()
    fake_llm_response.choices = [MagicMock(message=MagicMock(content="I'll go with option_b, it fits best."))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_llm_response

    with patch("src.decision_model.settings") as mock_settings, \
         patch("src.decision_model.llm_client", return_value=fake_client):
        mock_settings.decision_model_url = ""
        result = decide(options=["option_a", "option_b"], prompt="pick one")

    assert result.choice == "option_b"
    assert result.confidence == 0.5
    assert result.source == "llm_fallback"


def test_llm_fallback_raises_when_no_option_recoverable():
    fake_llm_response = MagicMock()
    fake_llm_response.choices = [MagicMock(message=MagicMock(content="completely unrelated gibberish"))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_llm_response

    with patch("src.decision_model.settings") as mock_settings, \
         patch("src.decision_model.llm_client", return_value=fake_client):
        mock_settings.decision_model_url = ""
        with pytest.raises(ValueError):
            decide(options=["option_a", "option_b"], prompt="pick one")


def test_decision_model_choice_outside_fixed_set_falls_back_to_llm():
    fake_response = MagicMock()
    fake_response.json.return_value = {"choice": "not_a_real_option", "confidence": 0.9}
    fake_response.raise_for_status.return_value = None

    fake_llm_response = MagicMock()
    fake_llm_response.choices = [MagicMock(message=MagicMock(content='{"choice": "a", "confidence": 0.7}'))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_llm_response

    with patch("src.decision_model.settings") as mock_settings, \
         patch("src.decision_model.requests.post", return_value=fake_response), \
         patch("src.decision_model.llm_client", return_value=fake_client):
        mock_settings.decision_model_url = "http://localhost:9999"
        result = decide(options=["a", "b"], prompt="pick one")

    assert result.choice == "a"
    assert result.source == "llm_fallback"


def test_choice_resolution_is_case_insensitive():
    fake_response = MagicMock()
    fake_response.json.return_value = {"choice": "VIOLATION", "confidence": 0.9}
    fake_response.raise_for_status.return_value = None

    with patch("src.decision_model.settings") as mock_settings, \
         patch("src.decision_model.requests.post", return_value=fake_response):
        mock_settings.decision_model_url = "http://localhost:9999"
        result = decide(options=["violation", "not_a_violation"], prompt="is this a violation?")

    assert result.choice == "violation"
