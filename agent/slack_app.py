"""Slack surface for the MsgStack agent — Events API (not Socket Mode; this
server already sits behind a public Cloudflare tunnel hostname), ASGI-mounted
alongside the rest of the FastAPI/Starlette stack for consistency with
run_server.py's PathRouter pattern.
"""

from __future__ import annotations

import logging
import re

from slack_bolt.adapter.starlette.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp
from starlette.applications import Starlette
from starlette.routing import Route

from agent.approval import log_approval
from agent.config import settings
from agent.core import AgentCore, AgentResponse
from agent.identity import IdentityStore

logger = logging.getLogger("agent.slack")

bolt_app = AsyncApp(
    # Bolt's constructor requires a token even for import-time construction
    # (e.g. under test, or before real secrets are configured); the
    # placeholder never reaches Slack's API — only a real SLACK_BOT_TOKEN does.
    token=settings.slack_bot_token or "xoxb-unconfigured",
    signing_secret=settings.slack_signing_secret,
)
_core = AgentCore()
_identity = IdentityStore()

_MENTION_RE = re.compile(r"<@[^>]+>\s*")


def _blocks_for(resp: AgentResponse) -> list[dict]:
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": resp.text[:2900]}}]
    if resp.error or not resp.domain_id:
        return blocks
    blocks.append({
        "type": "actions",
        "block_id": f"msgstack_actions|{resp.domain_id}|{resp.skill_id}",
        "elements": [
            {"type": "button", "action_id": "msgstack_approve", "style": "primary",
             "text": {"type": "plain_text", "text": "Approve"}, "value": resp.domain_id},
            {"type": "button", "action_id": "msgstack_edit",
             "text": {"type": "plain_text", "text": "Edit"}, "value": resp.text},
            {"type": "button", "action_id": "msgstack_regenerate",
             "text": {"type": "plain_text", "text": "Regenerate"}, "value": resp.domain_id},
        ],
    })
    return blocks


@bolt_app.event("app_mention")
async def handle_mention(event: dict, say) -> None:
    text = _MENTION_RE.sub("", event.get("text", "")).strip()
    user_id = event.get("user", "unknown")
    if not text:
        await say(text="Mention me with what you want, e.g. \"@MsgStack write a one-pager for <domain>\".",
                   thread_ts=event.get("ts"))
        return
    resp = await _core.handle_request(text, platform_user_id=user_id, platform="slack")
    await say(blocks=_blocks_for(resp), text=resp.text[:2900], thread_ts=event.get("ts"))


@bolt_app.action("msgstack_approve")
async def handle_approve(ack, body: dict, respond) -> None:
    await ack()
    domain_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    performed_by = _identity.resolve("slack", user_id)
    try:
        await log_approval(domain_id, performed_by)
        await respond(text=f"Approved by {performed_by}.", replace_original=False)
    except Exception:
        logger.exception("approval failed")
        await respond(text="Couldn't log the approval — check the MsgStack logs.", replace_original=False)


@bolt_app.action("msgstack_regenerate")
async def handle_regenerate(ack, body: dict, respond) -> None:
    await ack()
    # block_id carries "msgstack_actions|<domain_id>|<skill_id>" from _blocks_for above.
    block_id = body["actions"][0].get("block_id", "")
    parts = block_id.split("|")
    skill_id = parts[2] if len(parts) == 3 else "one_pager"
    domain_id = body["actions"][0]["value"]
    domains = await _core.list_domains()
    domain = next((d for d in domains if d.get("domain_id") == domain_id), None)
    if not domain:
        await respond(text="That domain no longer exists — can't regenerate.", replace_original=False)
        return
    resp = await _core.handle_request(
        f"write a {skill_id.replace('_', ' ')} for {domain['name']}",
        platform_user_id=body["user"]["id"], platform="slack",
    )
    await respond(blocks=_blocks_for(resp), text=resp.text[:2900], replace_original=False)


@bolt_app.action("msgstack_edit")
async def handle_edit(ack, body: dict, client) -> None:
    """No per-entry edit API exists server-side (see agent/approval.py's scope
    note) — this opens a modal so a human can produce a corrected draft to
    paste back, it does not write anything to MsgStack."""
    await ack()
    original = body["actions"][0]["value"]
    await client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "msgstack_edit_modal",
            "title": {"type": "plain_text", "text": "Edit draft"},
            "submit": {"type": "plain_text", "text": "Post edited version"},
            "blocks": [{
                "type": "input",
                "block_id": "edited_text_block",
                "label": {"type": "plain_text", "text": "Draft"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "edited_text",
                    "multiline": True,
                    "initial_value": original[:3000],
                },
            }],
        },
    )


@bolt_app.view("msgstack_edit_modal")
async def handle_edit_submit(ack, body: dict, view: dict, client) -> None:
    await ack()
    edited = view["state"]["values"]["edited_text_block"]["edited_text"]["value"]
    channel_id = body.get("user", {}).get("id")  # DM the editor; no channel id on a modal submit.
    await client.chat_postMessage(channel=channel_id, text=f"*Edited draft:*\n\n{edited}")


asgi_app = Starlette(routes=[
    Route("/slack/events", endpoint=AsyncSlackRequestHandler(bolt_app).handle, methods=["POST"]),
])
