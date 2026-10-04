"""Microsoft Teams surface for the MsgStack agent.

Built directly on the Bot Framework SDK for Python (botbuilder-core) rather
than "Teams AI Library" — that library is JS/.NET-first; its Python package
maturity for native MCP client support could not be verified at the time
this was written. Bot Framework SDK is what Teams AI Library itself wraps,
so this is the same underlying mechanism, just without that abstraction
layer. Shares agent/core.py's tool-calling loop with slack_app.py so the
two surfaces don't duplicate logic — only this file and slack_app.py differ.
"""

from __future__ import annotations

import logging

from botbuilder.core import (
    ActivityHandler,
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity, Attachment, ChannelAccount
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from agent.approval import log_approval
from agent.config import settings
from agent.core import AgentCore, AgentResponse
from agent.identity import IdentityStore

logger = logging.getLogger("agent.teams")

_core = AgentCore()
_identity = IdentityStore()

_adapter_settings = BotFrameworkAdapterSettings(settings.teams_app_id, settings.teams_app_password)
_adapter = BotFrameworkAdapter(_adapter_settings)


def _card_for(resp: AgentResponse) -> Attachment:
    body = [{"type": "TextBlock", "text": resp.text[:2900], "wrap": True}]
    actions = []
    if not resp.error and resp.domain_id:
        actions = [
            {"type": "Action.Submit", "title": "Approve",
             "data": {"msgstack_action": "approve", "domain_id": resp.domain_id}},
            {"type": "Action.Submit", "title": "Edit",
             "data": {"msgstack_action": "edit", "text": resp.text}},
            {"type": "Action.Submit", "title": "Regenerate",
             "data": {"msgstack_action": "regenerate", "domain_id": resp.domain_id,
                       "skill_id": resp.skill_id}},
        ]
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
        "actions": actions,
    }
    return Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card)


class MsgStackTeamsBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext) -> None:
        value = turn_context.activity.value
        if isinstance(value, dict) and value.get("msgstack_action"):
            await self._handle_action(turn_context, value)
            return

        text = TurnContext.remove_recipient_mention(turn_context.activity) or ""
        text = text.strip()
        user_id = turn_context.activity.from_property.id if turn_context.activity.from_property else "unknown"
        if not text:
            await turn_context.send_activity("Ask me for something, e.g. \"write a one-pager for <domain>\".")
            return
        resp = await _core.handle_request(text, platform_user_id=user_id, platform="teams")
        await turn_context.send_activity(Activity(type="message", attachments=[_card_for(resp)]))

    async def _handle_action(self, turn_context: TurnContext, value: dict) -> None:
        action = value["msgstack_action"]
        user_id = turn_context.activity.from_property.id if turn_context.activity.from_property else "unknown"

        if action == "approve":
            performed_by = _identity.resolve("teams", user_id)
            try:
                await log_approval(value["domain_id"], performed_by)
                await turn_context.send_activity(f"Approved by {performed_by}.")
            except Exception:
                logger.exception("approval failed")
                await turn_context.send_activity("Couldn't log the approval — check the MsgStack logs.")

        elif action == "regenerate":
            domains = await _core.list_domains()
            domain = next((d for d in domains if d.get("domain_id") == value.get("domain_id")), None)
            if not domain:
                await turn_context.send_activity("That domain no longer exists — can't regenerate.")
                return
            skill_id = value.get("skill_id") or "one_pager"
            resp = await _core.handle_request(
                f"write a {skill_id.replace('_', ' ')} for {domain['name']}",
                platform_user_id=user_id, platform="teams",
            )
            await turn_context.send_activity(Activity(type="message", attachments=[_card_for(resp)]))

        elif action == "edit":
            # No per-entry edit API exists server-side (agent/approval.py's scope
            # note) — point the editor at the content to paste-and-correct rather
            # than pretending this writes anything back to MsgStack.
            await turn_context.send_activity(
                f"Edit and repost this draft (nothing is saved automatically):\n\n{value.get('text', '')[:2900]}"
            )

    async def on_members_added_activity(self, members_added: list[ChannelAccount], turn_context: TurnContext) -> None:
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "Hi — ask me to write something grounded in a MsgStack canon domain, "
                    "e.g. \"write a battlecard for Acme Cloud Security Platform\"."
                )


_bot = MsgStackTeamsBot()


async def _messages(request: Request) -> Response:
    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    async def call_bot(turn_context: TurnContext) -> None:
        await _bot.on_turn(turn_context)

    await _adapter.process_activity(activity, auth_header, call_bot)
    return Response(status_code=201)


asgi_app = Starlette(routes=[Route("/teams/messages", endpoint=_messages, methods=["POST"])])
