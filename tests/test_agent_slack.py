"""Handler logic for the Slack surface, called directly rather than through
Bolt's dispatcher — that would mean standing up real signature verification
and HTTP plumbing to test business logic that doesn't depend on any of it.
"""

from unittest.mock import AsyncMock, patch

import pytest

from agent.core import AgentResponse
from agent.slack_app import _blocks_for, handle_approve, handle_mention, handle_regenerate


def test_blocks_for_includes_actions_when_domain_known():
    resp = AgentResponse(text="content", domain_id="d1", domain_name="Acme", skill_id="one_pager")
    blocks = _blocks_for(resp)
    assert blocks[0]["text"]["text"] == "content"
    action_block = blocks[1]
    action_ids = [el["action_id"] for el in action_block["elements"]]
    assert action_ids == ["msgstack_approve", "msgstack_edit", "msgstack_regenerate"]
    assert action_block["block_id"] == "msgstack_actions|d1|one_pager"


def test_blocks_for_omits_actions_on_error():
    resp = AgentResponse(text="failed", error=True)
    assert len(_blocks_for(resp)) == 1


@pytest.mark.asyncio
async def test_handle_mention_strips_mention_and_calls_core():
    say = AsyncMock()
    event = {"text": "<@U0BOT> write a one-pager for Acme", "user": "U1", "ts": "123.456"}
    with patch("agent.slack_app._core.handle_request", new=AsyncMock(
        return_value=AgentResponse(text="done", domain_id="d1", domain_name="Acme", skill_id="one_pager")
    )) as mocked:
        await handle_mention(event, say)
    mocked.assert_awaited_once_with("write a one-pager for Acme", platform_user_id="U1", platform="slack")
    say.assert_awaited_once()
    assert say.call_args.kwargs["thread_ts"] == "123.456"


@pytest.mark.asyncio
async def test_handle_mention_with_empty_text_asks_for_input():
    say = AsyncMock()
    await handle_mention({"text": "<@U0BOT>", "user": "U1", "ts": "1"}, say)
    say.assert_awaited_once()
    assert "Mention me" in say.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_handle_approve_logs_and_responds():
    ack = AsyncMock()
    respond = AsyncMock()
    body = {"actions": [{"value": "d1"}], "user": {"id": "U1"}}
    with patch("agent.slack_app.log_approval", new=AsyncMock(return_value={})) as log, \
         patch("agent.slack_app._identity.resolve", return_value="Abid Chaudhry"):
        await handle_approve(ack, body, respond)
    log.assert_awaited_once_with("d1", "Abid Chaudhry")
    ack.assert_awaited_once()
    assert "Abid Chaudhry" in respond.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_handle_approve_reports_failure_without_raising():
    ack = AsyncMock()
    respond = AsyncMock()
    body = {"actions": [{"value": "d1"}], "user": {"id": "U1"}}
    with patch("agent.slack_app.log_approval", new=AsyncMock(side_effect=RuntimeError("boom"))), \
         patch("agent.slack_app._identity.resolve", return_value="Abid Chaudhry"):
        await handle_approve(ack, body, respond)
    assert "Couldn't log the approval" in respond.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_handle_regenerate_reuses_the_same_domain_and_skill():
    ack = AsyncMock()
    respond = AsyncMock()
    body = {
        "actions": [{"value": "d2", "block_id": "msgstack_actions|d2|battlecard"}],
        "user": {"id": "U1"},
    }
    with patch("agent.slack_app._core.list_domains",
               new=AsyncMock(return_value=[{"domain_id": "d2", "name": "Helix HR"}])), \
         patch("agent.slack_app._core.handle_request", new=AsyncMock(
             return_value=AgentResponse(text="regenerated", domain_id="d2", skill_id="battlecard")
         )) as handle_request:
        await handle_regenerate(ack, body, respond)
    handle_request.assert_awaited_once_with(
        "write a battlecard for Helix HR", platform_user_id="U1", platform="slack"
    )
