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


class TestSchemaTypeDetection:
    """Regression: the content fallback used to match bare 'on-call' and
    'runbook', which appear in ordinary engineering specs, so real specs were
    misfiled as service_catalog on ingest."""

    def test_engineering_spec_is_the_default(self):
        from src.pipeline.structure import detect_document_type
        assert detect_document_type("Rate limit is 1000 req/min.", "payments-api.md") \
            == "engineering_spec"

    def test_passing_mention_of_oncall_does_not_redirect(self):
        from src.pipeline.structure import detect_document_type
        text = ("## Audiences\n### On-call SRE\nPaged against the error budget.\n"
                "## Runbook\n- Restart the pod.")
        assert detect_document_type(text, "payments-api.md") == "engineering_spec"

    def test_incident_detected_by_filename(self):
        from src.pipeline.structure import detect_document_type
        assert detect_document_type("Charges 504'd.", "incident-2026-07-14.md") \
            == "incident_record"

    def test_incident_detected_by_postmortem_language(self):
        from src.pipeline.structure import detect_document_type
        assert detect_document_type("Root cause: the timeout exceeded the ceiling.",
                                    "notes.md") == "incident_record"

    def test_policy_needs_a_real_policy_phrase(self):
        from src.pipeline.structure import detect_document_type
        assert detect_document_type("We use encryption at rest.", "x.md") == "policy_shield"
        # "security posture" alone is a section in every spec — must not redirect
        assert detect_document_type("## Security Posture\n- TLS 1.3 only.", "auth.md") \
            == "engineering_spec"

    def test_every_returned_type_is_a_live_schema_type(self):
        from src.models import SchemaType
        from src.pipeline.structure import detect_document_type
        live = {m.value for m in SchemaType}
        samples = [("a.md", "rate limit"), ("incident.md", "outage"),
                   ("policy.md", "gdpr"), ("catalog.md", "service owner"),
                   ("x.md", "root cause"), ("y.md", "data retention")]
        for name, text in samples:
            assert detect_document_type(text, name) in live


class TestStructurePromptIsEngineering:
    """The prompt was a mechanical rename of the PMM one — it still opened with
    'You are a messaging strategist' and asked for a tagline, so ingestion
    collapsed constraints and SLAs into 'capability'."""

    def test_prompt_does_not_ask_for_marketing_fields(self):
        from src.pipeline.structure import _STRUCTURE_PROMPT
        low = _STRUCTURE_PROMPT.lower()
        assert "messaging strategist" not in low
        assert "punchy" not in low
        assert "proof point" not in low
        # "objection" may appear only as a negative instruction telling the
        # model not to produce sales objections
        for line in (l.strip() for l in low.splitlines() if "objection" in l):
            assert line.startswith("call fails") or "not sales objections" in line, line

    def test_prompt_enumerates_the_engineering_assertion_types(self):
        from src.pipeline.structure import _STRUCTURE_PROMPT
        for t in ("constraint", "sla", "deprecation", "config_default",
                  "dependency", "interface_contract", "version_policy",
                  "runbook_step", "decision", "security_posture"):
            assert t in _STRUCTURE_PROMPT, f"{t} missing from structuring prompt"

    def test_prompt_protects_verbatim_content(self):
        from src.pipeline.structure import _STRUCTURE_PROMPT
        assert "verbatim" in _STRUCTURE_PROMPT.lower()
        assert "LOCKED" in _STRUCTURE_PROMPT


class TestSpecNameResolution:
    """Regression: ingestion named every spec after the document genre
    ("Internal API Documentation" x3) or after a section it liked ("Payments
    API Audience Profiles"). The name is the identifier edges and citations key
    off, so a wrong one is not recoverable downstream."""

    DOC = "# payments-api\n\nCard and wallet payment capture for checkout.\n\n## Constraints\n- 1000 req/min."

    def test_heading_wins_over_generic_llm_name(self):
        from src.pipeline.structure import resolve_spec_name
        for bad in ("Internal API Documentation", "Technical System Documentation",
                    "Service Overview", "Documentation", "API"):
            assert resolve_spec_name(bad, self.DOC, "payments-api.md") == "payments-api"

    def test_heading_wins_over_section_derived_name(self):
        from src.pipeline.structure import resolve_spec_name
        assert resolve_spec_name("Payments API Audience Profiles", self.DOC,
                                 "payments-api.md") == "payments-api"

    def test_heading_preserved_verbatim_including_case_and_hyphens(self):
        from src.pipeline.structure import resolve_spec_name
        assert resolve_spec_name("Payments API", self.DOC, "x.md") == "payments-api"

    def test_llm_name_used_when_document_has_no_heading(self):
        from src.pipeline.structure import resolve_spec_name
        text = "Extracted PDF body with no markdown headings whatsoever."
        assert resolve_spec_name("Acme Billing Service", text, "f.md") == "Acme Billing Service"

    def test_falls_back_to_source_name_when_both_are_useless(self):
        from src.pipeline.structure import resolve_spec_name
        assert resolve_spec_name("Documentation", "no headings here", "f.md") == "f.md"
        assert resolve_spec_name("", "no headings here", "f.md") == "f.md"

    def test_heading_only_taken_from_the_top_of_the_document(self):
        """A body paragraph before the first heading means the heading is not a
        title — do not take it."""
        from src.pipeline.structure import resolve_spec_name
        text = "Some preamble prose.\n\n# Appendix A\n\nmore"
        assert resolve_spec_name("Acme Service", text, "f.md") == "Acme Service"


class TestPromptCarriesTheDocument:
    """Regression: the rewritten engineering prompt lost its {content}
    placeholder. .replace() then did nothing, the model received an empty
    SOURCE DOCUMENT, and it invented an entire plausible API spec — correct
    shape, correct assertion types, completely fabricated facts. Nothing in the
    output distinguished it from a real extraction."""

    def test_every_prompt_template_carries_its_source_text(self):
        """Templates use either {content} (str.replace) or {text} (str.format).
        Either is fine; having neither means the document never reaches the
        model."""
        from src.pipeline import structure
        names = [n for n in dir(structure) if n.endswith("_PROMPT")]
        assert names, "no prompt templates found"
        for n in names:
            tpl = getattr(structure, n)
            assert "{content}" in tpl or "{text}" in tpl, \
                f"{n} has no source-text placeholder; the document cannot reach the model"

    def test_prompt_map_values_all_carry_the_placeholder(self):
        from src.pipeline.structure import SpecStructurer
        for schema_type, template in SpecStructurer._PROMPT_MAP.items():
            assert "{content}" in template, f"prompt for {schema_type} lost {{content}}"

    def test_structuring_refuses_a_template_without_the_placeholder(self):
        from src.pipeline.structure import SpecStructurer
        import pytest
        s = SpecStructurer.__new__(SpecStructurer)
        s._usage = {"input_tokens": 0, "output_tokens": 0}
        with pytest.raises(ValueError, match="placeholder"):
            s._structure_single_chunk("some document text", "doc.md", "PROMPT WITHOUT IT")


class TestLockedMarkerHandling:
    """A [LOCKED] marker is metadata about a fact, not part of it. The
    structurer is told both to split compound sentences and to reproduce the
    marker verbatim, so it emitted "**[LOCKED]**" as a standalone assertion."""

    def test_marker_detected_and_stripped(self):
        from src.web_app import _LOCKED_MARKER_RE as r
        t = "Rate limit is 1000 requests/minute. **[LOCKED]**"
        assert r.search(t)
        assert r.sub("", t).strip(" -—\t") == "Rate limit is 1000 requests/minute."

    def test_marker_only_fragment_reduces_to_empty(self):
        from src.web_app import _LOCKED_MARKER_RE as r
        assert r.sub("", "**[LOCKED]**").strip(" -—\t") == ""

    def test_bare_and_bold_forms_both_match(self):
        from src.web_app import _LOCKED_MARKER_RE as r
        for form in ("[LOCKED]", "**[LOCKED]**", "[locked]"):
            assert r.search(f"TLS 1.3 only {form}")

    def test_unmarked_content_is_untouched(self):
        from src.web_app import _LOCKED_MARKER_RE as r
        t = "Access tokens live 3600s."
        assert not r.search(t)
        assert r.sub("", t) == t


class TestCommitPathSymbolsResolve:
    """Regression: the LOCKED-marker handling referenced ContentTier, which
    web_app never imported. The conditional short-circuits, so only documents
    that actually contained [LOCKED] raised NameError — two of five — and the
    sync caught it, logged, and still reported "5 files ingested"."""

    def test_commit_path_names_are_all_importable(self):
        import src.web_app as w
        for name in ("Assertion", "AssertionStatus", "AssertionType",
                     "ContentTier", "Channel", "Spec", "SchemaType",
                     "Audience", "_LOCKED_MARKER_RE"):
            assert hasattr(w, name), f"web_app is missing {name}, used on the ingest path"

    def test_locked_branch_constructs_an_assertion(self):
        """Exercise the branch that only fires for [LOCKED] content."""
        from uuid import uuid4
        from src.models import Assertion, AssertionStatus, AssertionType, ContentTier
        a = Assertion(
            spec_id=uuid4(), assertion_type=AssertionType.CONSTRAINT, priority=1,
            content="Rate limit is 1000 requests/minute.",
            status=AssertionStatus.LOCKED, content_tier=ContentTier.TIER_1_LOCKED,
        )
        assert str(a.status) == "locked"
        assert str(a.content_tier) == "tier_1_locked"
