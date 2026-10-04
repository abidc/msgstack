"""Shared tool-calling loop for the Slack and Teams agents.

Both platform adapters (slack_app.py, teams_app.py) call into AgentCore —
this is the one place that talks MCP to the MsgStack server, so the two
surfaces never duplicate that logic.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from agent.config import settings

try:
    import httpx2 as _httpx  # mcp>=2.x's vendored client
except ImportError:
    import httpx as _httpx  # mcp 1.x uses plain httpx

logger = logging.getLogger("agent.core")

# generate_artifact's documented skill_id vocabulary (src/server.py docstring).
KNOWN_SKILLS = {
    "one_pager": ["one-pager", "one pager", "onepager"],
    "linkedin_post": ["linkedin post", "linkedin"],
    "email_template": ["email"],
    "battlecard": ["battlecard", "battle card"],
    "press_release": ["press release"],
    "blog_post": ["blog post", "blog"],
    "faq_document": ["faq"],
    "talk_track": ["talk track"],
    "objection_handler": ["objection handler", "objections"],
    "event_brief": ["event brief"],
    "executive_summary": ["executive summary", "exec summary"],
    "partner_brief": ["partner brief"],
}
DEFAULT_SKILL = "one_pager"


@dataclass
class AgentResponse:
    text: str
    domain_name: str | None = None
    domain_id: str | None = None
    skill_id: str | None = None
    error: bool = False
    available_domains: list[str] = field(default_factory=list)


@asynccontextmanager
async def mcp_session():
    """Open an MCP ClientSession against the MsgStack server, basic-auth included
    (the whole app, /mcp included, sits behind BasicAuthMiddleware — see run_server.py)."""
    auth = None
    if settings.msgstack_basic_user:
        auth = (settings.msgstack_basic_user, settings.msgstack_basic_pass)
    async with _httpx.AsyncClient(auth=auth, timeout=60.0) as http_client:
        async with streamable_http_client(
            settings.msgstack_mcp_url, http_client=http_client
        ) as streams:
            # mcp>=2.x yields (read, write); mcp 1.x yields (read, write, get_session_id).
            read_stream, write_stream = streams[0], streams[1]
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session


def _extract_tool_text(result) -> str:
    """CallToolResult.content is a list of content blocks; MsgStack's tools
    return plain text, so the first text block is the whole payload."""
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text is not None:
            return text
    return str(result)


def _guess_skill(text: str) -> str:
    lowered = text.lower()
    for skill_id, phrases in KNOWN_SKILLS.items():
        if any(p in lowered for p in phrases):
            return skill_id
    return DEFAULT_SKILL


def _skill_phrase_matched(text: str) -> bool:
    """Whether _guess_skill found a real phrase match, as opposed to falling through to
    DEFAULT_SKILL — can't tell those apart from the returned value alone, since
    DEFAULT_SKILL is itself a value _guess_skill can also return via a real match."""
    lowered = text.lower()
    return any(p in lowered for phrases in KNOWN_SKILLS.values() for p in phrases)


def _guess_domain(text: str, domains: list[dict]) -> dict | None:
    """Pick the canon domain whose name appears in the request text.
    Longest-name-first so "Acme Cloud Security Platform" wins over a
    coincidental substring match on a shorter unrelated name."""
    lowered = text.lower()
    for d in sorted(domains, key=lambda d: len(d["name"]), reverse=True):
        if d["name"].lower() in lowered:
            return d
    return None


class AgentCore:
    """One handle_request() call = one list_canon_domains + one generate_artifact
    MCP round trip. Stateless by design — platform adapters own any per-conversation
    state (e.g. "which domain did we just talk about")."""

    async def list_domains(self) -> list[dict]:
        """Returns [{"name": ..., "domain_id": ...}, ...] per list_canon_domains'
        documented `domains` key (src/server.py)."""
        async with mcp_session() as session:
            result = await session.call_tool("list_canon_domains", {})
            text = _extract_tool_text(result)
            return self._parse_domain_list(text)

    @staticmethod
    def _parse_domain_list(text: str) -> list[dict]:
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            logger.warning("list_canon_domains did not return JSON; got: %.200s", text)
            return []
        domains = parsed.get("domains") if isinstance(parsed, dict) else None
        if not isinstance(domains, list):
            return []
        return [
            {"name": d.get("name"), "domain_id": d.get("domain_id") or d.get("id")}
            for d in domains
            if d.get("name")
        ]

    async def _classify_via_mcp(self, text: str, options: list[str], context: str = "") -> str | None:
        """Ask the server's classify_request tool to pick one of `options`. None on failure —
        callers keep their existing heuristic result rather than failing the whole request
        over a routing refinement."""
        if len(options) < 2:
            return None
        try:
            async with mcp_session() as session:
                result = await session.call_tool(
                    "classify_request", {"text": text, "options": options, "context": context}
                )
                parsed = json.loads(_extract_tool_text(result))
                choice = parsed.get("choice")
                return choice if choice in options else None
        except Exception:
            logger.warning("classify_request MCP call failed; keeping heuristic result", exc_info=True)
            return None

    async def handle_request(self, text: str, platform_user_id: str, platform: str) -> AgentResponse:
        skill_id = _guess_skill(text)
        if not _skill_phrase_matched(text):
            # No phrase matched — ask the server for a real classification rather than
            # silently defaulting to one_pager for every ambiguous request.
            refined = await self._classify_via_mcp(text, list(KNOWN_SKILLS.keys()))
            if refined:
                skill_id = refined

        try:
            domains = await self.list_domains()
        except Exception:
            logger.exception("list_canon_domains failed")
            return AgentResponse(
                text="I couldn't reach MsgStack's grounding server just now — try again shortly.",
                error=True,
            )

        domain = _guess_domain(text, domains)
        domain_names = [d["name"] for d in domains]
        if domain is None and domain_names:
            refined_name = await self._classify_via_mcp(
                text, domain_names, context="Which canon domain is this request about?"
            )
            if refined_name:
                domain = next((d for d in domains if d["name"] == refined_name), None)
        if domain is None:
            if not domain_names:
                return AgentResponse(
                    text="No canon domains are set up yet in MsgStack.", error=True
                )
            return AgentResponse(
                text=(
                    "Which canon domain should I ground this in? Say the domain name, e.g. "
                    f"\"write a {skill_id.replace('_', ' ')} for {domain_names[0]}\"."
                ),
                available_domains=domain_names,
            )

        domain_name = domain["name"]
        try:
            async with mcp_session() as session:
                result = await session.call_tool(
                    "generate_artifact",
                    {"skill_id": skill_id, "domain_name": domain_name},
                )
                content = _extract_tool_text(result)
        except Exception:
            logger.exception("generate_artifact failed")
            return AgentResponse(
                text=f"Generation failed for {domain_name} — check the MsgStack logs.",
                domain_name=domain_name,
                domain_id=domain.get("domain_id"),
                skill_id=skill_id,
                error=True,
            )

        return AgentResponse(
            text=f"*Grounded in canon domain: {domain_name}*\n\n{content}",
            domain_name=domain_name,
            domain_id=domain.get("domain_id"),
            skill_id=skill_id,
        )
