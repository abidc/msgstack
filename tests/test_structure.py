"""Unit tests for src/pipeline/structure.py"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")

from src.pipeline.structure import SpecStructurer, StructuredSpec

CANONICAL_MARKDOWN = """# Acme Cloud Security

## Know Your Market
**Vision:** Secure the cloud-native enterprise
**Audience:** Security teams at mid-market SaaS companies
**Before:** Manual, slow, error-prone security reviews
**After:** Automated, instant, policy-as-code security
**Key Problem:** Cloud misconfigurations cause 80% of breaches
**Solution:** Automated policy enforcement with guardrails
**Credibility:** 500+ enterprise customers, SOC2 certified
**FOMO:** Breaches cost $4.2M on average
**Competition:** Manual tools, Wiz, Prisma Cloud
**The Win:** Zero breach guarantee
**Call to Action:** Start free trial

## Summary
Acme Cloud Security automates infrastructure security for DevOps teams.
It enforces policy-as-code and prevents misconfigurations before deploy.

## Target Audience
Security engineers and DevOps leads at mid-market SaaS companies (100-500 employees).

## Brand Personality
Precise, confident, technical without being jargon-heavy.

## Positioning
For DevOps teams who ship fast, Acme is the only security platform that enforces policy-as-code before deployment. Unlike manual review tools, Acme prevents misconfigurations automatically.

## Tagline
Ship fast. Stay secure.

## Differentiation
Only platform with pre-deploy enforcement. No agent required. SOC2 certified.

## Assertions

### Capabilities (Priority 1-2)
- Ship fast. Stay secure.
- Automate security before it becomes a breach.

### Capabilities (Priority 1-3)
- Prevent 80% of cloud misconfigurations automatically
- Deploy in minutes, not months

### Capabilities (Priority 1-3)
- CI/CD pipeline integration for automated policy checks

### SLAs (Priority 1-3)
- Acme customer reduced breach incidents by 90% in Q1

### Limitations (Priority 1-2)
- "Too complex to implement" — deploys in under 30 minutes, no agent

## Personas

### Security Engineer
**Role:** Senior security engineer at a 200-person SaaS company
**Pain Points:** Manual reviews slow down deployments
**Buying Triggers:** Recent audit failure or near-miss incident
**Objections:** Concerned about alert fatigue
"""


@pytest.fixture
def structurer():
    with patch("src.config.llm_client"):
        s = SpecStructurer(openai_api_key="test-key")
    return s


# ── _parse_markdown ───────────────────────────────────────────────────────────

class TestParseMarkdown:
    def test_extracts_name(self, structurer):
        spec = structurer._parse_markdown(CANONICAL_MARKDOWN, "fallback")
        assert spec.name == "Acme Cloud Security"

    def test_extracts_summary(self, structurer):
        spec = structurer._parse_markdown(CANONICAL_MARKDOWN, "x")
        assert "DevOps" in spec.summary

    def test_extracts_audience(self, structurer):
        spec = structurer._parse_markdown(CANONICAL_MARKDOWN, "x")
        assert "Security engineers" in spec.audience

    def test_extracts_positioning(self, structurer):
        spec = structurer._parse_markdown(CANONICAL_MARKDOWN, "x")
        assert "policy-as-code" in spec.positioning

    def test_extracts_tagline(self, structurer):
        spec = structurer._parse_markdown(CANONICAL_MARKDOWN, "x")
        assert "Ship fast" in spec.tagline

    def test_extracts_differentiation(self, structurer):
        spec = structurer._parse_markdown(CANONICAL_MARKDOWN, "x")
        assert "pre-deploy" in spec.differentiation

    def test_extracts_know_your_market(self, structurer):
        spec = structurer._parse_markdown(CANONICAL_MARKDOWN, "x")
        assert "Vision" in spec.know_your_market or "Secure" in spec.know_your_market

    def test_fallback_name_when_no_h1(self, structurer):
        md = "## Summary\nSome summary"
        spec = structurer._parse_markdown(md, "My Source")
        assert spec.name == "My Source"

    def test_missing_sections_detected(self, structurer):
        md = "# Minimal\n\n## Summary\nA summary\n"
        spec = structurer._parse_markdown(md, "x")
        assert "tagline" in spec.missing_sections or len(spec.missing_sections) > 0

    def test_returns_structured_spec(self, structurer):
        spec = structurer._parse_markdown(CANONICAL_MARKDOWN, "x")
        assert isinstance(spec, StructuredSpec)


# ── _parse_key_messages ───────────────────────────────────────────────────────

class TestParseKeyMessages:
    def test_headline_section(self, structurer):
        text = "### Capabilities (Priority 1-2)\n- Ship fast. Stay secure.\n- Automate now."
        msgs = structurer._parse_key_messages(text)
        assert len(msgs) == 2
        assert all(m["assertion_type"] == "capability" for m in msgs)

    def test_benefit_section(self, structurer):
        text = "### Capabilities (Priority 1-3)\n- Reduce cost by 40%\n- Deploy in minutes"
        msgs = structurer._parse_key_messages(text)
        assert all(m["assertion_type"] == "capability" for m in msgs)

    def test_proof_point_section(self, structurer):
        text = "### SLAs (Priority 1-3)\n- Acme reduced incidents by 90%"
        msgs = structurer._parse_key_messages(text)
        assert msgs[0]["assertion_type"] == "sla"

    def test_qa_pair_section(self, structurer):
        text = "### Limitations (Priority 1-2)\n- Too complex — deploys in 30 min"
        msgs = structurer._parse_key_messages(text)
        assert msgs[0]["assertion_type"] == "limitation"

    def test_use_case_section(self, structurer):
        text = "### Capabilities (Priority 1-3)\n- CI/CD integration for policy enforcement"
        msgs = structurer._parse_key_messages(text)
        assert msgs[0]["assertion_type"] == "capability"

    def test_priority_suffix_stripped(self, structurer):
        """'(Priority 1-2)' suffix in header name should not break section detection."""
        text = "### Capabilities (Priority 1-2)\n- My headline"
        msgs = structurer._parse_key_messages(text)
        assert msgs[0]["assertion_type"] == "capability"

    def test_skips_not_found_placeholder(self, structurer):
        text = "### Capabilities (Priority 1-3)\n- [Not found in source]"
        msgs = structurer._parse_key_messages(text)
        assert len(msgs) == 0

    def test_multiple_sections(self, structurer):
        text = ("### Capabilities (Priority 1-2)\n- H1\n"
                "### Capabilities (Priority 1-3)\n- B1\n- B2")
        msgs = structurer._parse_key_messages(text)
        types = [m["assertion_type"] for m in msgs]
        assert "capability" in types
        assert "capability" in types
        assert len(msgs) == 3

    def test_default_fields(self, structurer):
        text = "### Capabilities (Priority 1-3)\n- Value here"
        msgs = structurer._parse_key_messages(text)
        assert msgs[0]["variants"] == {}
        assert msgs[0]["audiences"] == []
        assert msgs[0]["channels"] == ["all"]

    def test_empty_text(self, structurer):
        assert structurer._parse_key_messages("") == []


# ── _parse_audiences (regex fallback) ─────────────────────────────────────────

class TestParsePersonasRegex:
    def test_extracts_name(self, structurer):
        text = "### Security Engineer\n**Role:** Senior engineer\n- Pain one\n"
        audiences = structurer._parse_audiences_regex(text)
        assert len(audiences) == 1
        assert audiences[0]["name"] == "Security Engineer"

    def test_extracts_role(self, structurer):
        text = "### CISO\n**Role:** Chief Information Security Officer\n"
        audiences = structurer._parse_audiences_regex(text)
        assert "Chief Information Security Officer" in audiences[0]["description"]

    def test_multiple_audiences(self, structurer):
        text = ("### Dev Lead\n**Role:** Lead developer\n\n"
                "### DevOps Engineer\n**Role:** Platform engineer\n")
        audiences = structurer._parse_audiences_regex(text)
        assert len(audiences) == 2

    def test_skips_not_found(self, structurer):
        text = "### DevOps\n**Role:** Engineer\n- [Not found in source]"
        audiences = structurer._parse_audiences_regex(text)
        assert audiences[0].get("qa_pairs", []) == [] or "[Not found" not in str(audiences[0]["qa_pairs"])

    def test_empty_text(self, structurer):
        assert structurer._parse_audiences_regex("") == []


# ── _merge_structures ─────────────────────────────────────────────────────────

class TestMergeStructures:
    def test_single_chunk_returned_as_is(self, structurer):
        h = StructuredSpec(name="X", summary="s", audience="a", brand_personality="b",
                            positioning="p", tagline="t", differentiation="d",
                            assertions=[], audiences=[])
        result = structurer._merge_structures([h], "X")
        assert result.name == "X"

    def test_deduplicates_key_messages(self, structurer):
        msg = {"assertion_type": "capability", "priority": 1, "content": "Reduce cost by 40%",
               "variants": {}, "audiences": [], "channels": ["all"]}
        h1 = StructuredSpec(name="A", summary="s", audience="a", brand_personality="b",
                             positioning="p", tagline="t", differentiation="d",
                             assertions=[msg], audiences=[])
        h2 = StructuredSpec(name="A", summary="s", audience="a", brand_personality="b",
                             positioning="p", tagline="t", differentiation="d",
                             assertions=[msg], audiences=[])
        result = structurer._merge_structures([h1, h2], "A")
        assert len(result.assertions) == 1

    def test_merges_distinct_messages(self, structurer):
        m1 = {"assertion_type": "capability", "priority": 1, "content": "Save time",
               "variants": {}, "audiences": [], "channels": ["all"]}
        m2 = {"assertion_type": "capability", "priority": 1, "content": "Cut costs",
               "variants": {}, "audiences": [], "channels": ["all"]}
        h1 = StructuredSpec(name="A", summary="s", audience="a", brand_personality="b",
                             positioning="p", tagline="t", differentiation="d",
                             assertions=[m1], audiences=[])
        h2 = StructuredSpec(name="A", summary="s2", audience="a2", brand_personality="b2",
                             positioning="p2", tagline="t2", differentiation="d2",
                             assertions=[m2], audiences=[])
        result = structurer._merge_structures([h1, h2], "A")
        assert len(result.assertions) == 2

    def test_takes_first_nonempty_fields(self, structurer):
        h1 = StructuredSpec(name="", summary="", audience="a", brand_personality="b",
                             positioning="p", tagline="", differentiation="d",
                             assertions=[], audiences=[])
        h2 = StructuredSpec(name="B", summary="s2", audience="a2", brand_personality="b2",
                             positioning="p2", tagline="t2", differentiation="d2",
                             assertions=[], audiences=[])
        result = structurer._merge_structures([h1, h2], "fallback")
        assert result.summary == "s2"
        assert result.tagline == "t2"

    def test_deduplicates_audiences_by_name(self, structurer):
        p = {"name": "DevOps Lead", "description": "Lead",
              "buying_triggers": [], "qa_pairs": []}
        h1 = StructuredSpec(name="A", summary="s", audience="a", brand_personality="b",
                             positioning="p", tagline="t", differentiation="d",
                             assertions=[], audiences=[p])
        h2 = StructuredSpec(name="A", summary="s", audience="a", brand_personality="b",
                             positioning="p", tagline="t", differentiation="d",
                             assertions=[], audiences=[p])
        result = structurer._merge_structures([h1, h2], "A")
        assert len(result.audiences) == 1


# ── to_markdown ───────────────────────────────────────────────────────────────

class TestToMarkdown:
    def test_roundtrip_preserves_name(self, structurer):
        spec = structurer._parse_markdown(CANONICAL_MARKDOWN, "x")
        md = structurer.to_markdown(spec)
        assert "# Acme Cloud Security" in md

    def test_roundtrip_preserves_tagline(self, structurer):
        spec = structurer._parse_markdown(CANONICAL_MARKDOWN, "x")
        md = structurer.to_markdown(spec)
        assert "Ship fast" in md

    def test_includes_key_messages(self, structurer):
        spec = structurer._parse_markdown(CANONICAL_MARKDOWN, "x")
        md = structurer.to_markdown(spec)
        assert "## Assertions" in md
