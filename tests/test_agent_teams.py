"""Handler logic for the Teams surface. on_message_activity is called
directly against a fake TurnContext rather than going through the Bot
Framework adapter's auth/activity-processing pipeline, for the same reason
test_agent_slack.py bypasses Bolt's dispatcher: that pipeline isn't this
package's logic to test."""

from unittest.mock import AsyncMock, patch

import pytest
from botbuilder.schema import Activity, ChannelAccount

from agent.core import AgentResponse
from agent.teams_app import MsgStackTeamsBot, _card_for


def _activity(text=None, value=None, from_id="U1"):
    return Activity(
        type="message",
        text=text,
        value=value,
        recipient=ChannelAccount(id="bot1"),
        from_property=ChannelAccount(id=from_id),
        entities=[],
    )


class FakeTurnContext:
    def __init__(self, activity):
        self.activity = activity
        self.send_activity = AsyncMock()


def test_card_for_includes_actions_when_domain_known():
    resp = AgentResponse(text="content", domain_id="d1", domain_name="Acme", skill_id="one_pager")
    attachment = _card_for(resp)
    actions = attachment.content["actions"]
    assert [a["title"] for a in actions] == ["Approve", "Edit", "Regenerate"]
    assert actions[0]["data"]["domain_id"] == "d1"


def test_card_for_omits_actions_on_error():
    resp = AgentResponse(text="failed", error=True)
    assert _card_for(resp).content["actions"] == []


@pytest.mark.asyncio
async def test_on_message_activity_strips_mention_and_calls_core():
    ctx = FakeTurnContext(_activity(text="write a one-pager for Acme"))
    bot = MsgStackTeamsBot()
    with patch("agent.teams_app._core.handle_request", new=AsyncMock(
        return_value=AgentResponse(text="done", domain_id="d1", domain_name="Acme", skill_id="one_pager")
    )) as mocked:
        await bot.on_message_activity(ctx)
    mocked.assert_awaited_once_with("write a one-pager for Acme", platform_user_id="U1", platform="teams")
    ctx.send_activity.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_message_activity_routes_approve_action_payload():
    ctx = FakeTurnContext(_activity(value={"msgstack_action": "approve", "domain_id": "d1"}))
    bot = MsgStackTeamsBot()
    with patch("agent.teams_app.log_approval", new=AsyncMock(return_value={})) as log, \
         patch("agent.teams_app._identity.resolve", return_value="Abid Chaudhry"):
        await bot.on_message_activity(ctx)
    log.assert_awaited_once_with("d1", "Abid Chaudhry")
    assert "Abid Chaudhry" in ctx.send_activity.call_args.args[0]


@pytest.mark.asyncio
async def test_on_message_activity_routes_edit_action_without_calling_backend():
    ctx = FakeTurnContext(_activity(value={"msgstack_action": "edit", "text": "draft text"}))
    bot = MsgStackTeamsBot()
    with patch("agent.teams_app.log_approval", new=AsyncMock()) as log:
        await bot.on_message_activity(ctx)
    log.assert_not_awaited()
    assert "draft text" in ctx.send_activity.call_args.args[0]


@pytest.mark.asyncio
async def test_on_message_activity_routes_regenerate_action():
    ctx = FakeTurnContext(_activity(value={"msgstack_action": "regenerate", "domain_id": "d2", "skill_id": "battlecard"}))
    bot = MsgStackTeamsBot()
    with patch("agent.teams_app._core.list_domains",
               new=AsyncMock(return_value=[{"domain_id": "d2", "name": "Helix HR"}])), \
         patch("agent.teams_app._core.handle_request", new=AsyncMock(
             return_value=AgentResponse(text="regenerated", domain_id="d2", skill_id="battlecard")
         )) as handle_request:
        await bot.on_message_activity(ctx)
    handle_request.assert_awaited_once_with(
        "write a battlecard for Helix HR", platform_user_id="U1", platform="teams"
    )
