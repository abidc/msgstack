"""Tool-calling loop logic shared by the Slack and Teams agents.

Mocks agent.core.mcp_session itself rather than digging into the real mcp
ClientSession — this package's contract with the MCP server is "call
list_canon_domains then generate_artifact and parse their text content",
not the transport mechanics mcp_session wraps.
"""

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent.core import AgentCore, _guess_domain, _guess_skill, _extract_tool_text


def _tool_result(text: str):
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


class FakeSession:
    def __init__(self, domains_json: str, generate_text: str = "generated content"):
        self._domains_json = domains_json
        self._generate_text = generate_text
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, args: dict):
        self.calls.append((name, args))
        if name == "list_canon_domains":
            return _tool_result(self._domains_json)
        if name == "generate_artifact":
            return _tool_result(self._generate_text)
        raise AssertionError(f"unexpected tool call: {name}")


def _patched_session(monkeypatch, fake_session: FakeSession):
    @asynccontextmanager
    async def _fake_mcp_session():
        yield fake_session

    monkeypatch.setattr("agent.core.mcp_session", _fake_mcp_session)


DOMAINS_JSON = json.dumps({
    "domains": [
        {"domain_id": "d1", "name": "Acme Cloud Security Platform"},
        {"domain_id": "d2", "name": "Helix HR"},
    ]
})


def test_guess_skill_defaults_to_one_pager():
    assert _guess_skill("tell me something") == "one_pager"


def test_guess_skill_matches_keyword():
    assert _guess_skill("write a battlecard for Acme") == "battlecard"
    assert _guess_skill("draft a LinkedIn post") == "linkedin_post"


def test_guess_domain_prefers_longest_match():
    domains = [{"name": "Helix"}, {"name": "Helix HR"}]
    # "Helix HR" should win even though "Helix" also matches as a substring.
    assert _guess_domain("write about Helix HR please", domains)["name"] == "Helix HR"


def test_guess_domain_no_match_returns_none():
    assert _guess_domain("nothing matches here", [{"name": "Acme"}]) is None


def test_extract_tool_text_reads_first_text_block():
    result = _tool_result("hello")
    assert _extract_tool_text(result) == "hello"


@pytest.mark.asyncio
async def test_handle_request_asks_for_domain_when_ambiguous(monkeypatch):
    _patched_session(monkeypatch, FakeSession(DOMAINS_JSON))
    core = AgentCore()
    resp = await core.handle_request("write a one-pager", "U1", "slack")
    assert resp.domain_id is None
    assert "Which canon domain" in resp.text
    assert resp.available_domains == ["Acme Cloud Security Platform", "Helix HR"]


@pytest.mark.asyncio
async def test_handle_request_generates_when_domain_named(monkeypatch):
    fake = FakeSession(DOMAINS_JSON, generate_text="the one-pager body")
    _patched_session(monkeypatch, fake)
    core = AgentCore()
    resp = await core.handle_request("write a one-pager for Helix HR", "U1", "slack")
    assert resp.domain_id == "d2"
    assert resp.domain_name == "Helix HR"
    assert resp.skill_id == "one_pager"
    assert "the one-pager body" in resp.text
    assert fake.calls[-1] == ("generate_artifact", {"skill_id": "one_pager", "domain_name": "Helix HR"})


@pytest.mark.asyncio
async def test_handle_request_no_domains_configured(monkeypatch):
    _patched_session(monkeypatch, FakeSession(json.dumps({"domains": []})))
    core = AgentCore()
    resp = await core.handle_request("write a one-pager", "U1", "slack")
    assert resp.error is True
    assert "No canon domains" in resp.text


@pytest.mark.asyncio
async def test_handle_request_generation_failure_is_reported_not_raised(monkeypatch):
    fake = FakeSession(DOMAINS_JSON)

    async def _boom(name, args):
        raise RuntimeError("tool call failed")

    fake.call_tool = AsyncMock(side_effect=[_tool_result(DOMAINS_JSON), RuntimeError("boom")])
    _patched_session(monkeypatch, fake)
    core = AgentCore()
    resp = await core.handle_request("write a one-pager for Helix HR", "U1", "slack")
    assert resp.error is True
    assert resp.domain_name == "Helix HR"


@pytest.mark.asyncio
async def test_list_domains_tolerates_non_json_response(monkeypatch):
    _patched_session(monkeypatch, FakeSession("not json at all"))
    core = AgentCore()
    domains = await core.list_domains()
    assert domains == []
