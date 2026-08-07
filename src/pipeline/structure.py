"""LLM-based Spec structuring: raw text → structured markdown."""

import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from openai import OpenAI, APITimeoutError, RateLimitError, APIError
from pydantic import BaseModel, Field, field_validator

log = logging.getLogger(__name__)


def detect_document_type(text: str, filename: str = "") -> str:
    """Heuristic document type detection from filename and content keywords."""
    name_lower = (filename or "").lower()
    text_lower = text[:2000].lower()

    if any(k in name_lower for k in ("brand", "style guide", "voice", "tone")):
        return "brand_guide"
    if any(k in name_lower for k in ("competitive", "competitor", "battle card")):
        return "competitive_brief"
    if any(k in name_lower for k in ("narrative", "story", "about us", "company")):
        return "corp_narrative"
    if any(k in name_lower for k in ("persona", "buyer", "icp")):
        return "persona_library"

    # Content-based fallback
    if any(k in text_lower for k in ("message house", "key message", "positioning statement", "tagline", "pillar")):
        return "message_house"
    if any(k in text_lower for k in ("brand voice", "writing style", "word list", "do not use")):
        return "brand_guide"
    if any(k in text_lower for k in ("competitor", "vs.", " vs ", "battle card")):
        return "competitive_brief"
    if any(k in text_lower for k in ("persona", "buyer", "pain point", "buying trigger")):
        return "persona_library"

    return "message_house"  # default


class StructuredSpec(BaseModel):
    name: str
    summary: str
    audience: str
    brand_personality: str
    positioning: str
    tagline: str
    differentiation: str
    assertions: list[dict] = Field(default_factory=list)
    personas: list[dict]
    pillars: list[dict] = Field(default_factory=list)
    ungrouped_chunks: list[dict] = Field(default_factory=list)
    know_your_market: str = Field(default="")
    missing_sections: list[str] = Field(default_factory=list)

    @field_validator("know_your_market", mode="before")
    @classmethod
    def coerce_kym_to_str(cls, v):
        if isinstance(v, dict):
            return json.dumps(v)
        return v if isinstance(v, str) else str(v) if v is not None else ""

REQUIRED_SECTIONS = ["summary", "audience", "positioning", "tagline", "differentiation"]
REQUIRED_MESSAGE_TYPES = ["headline", "benefit", "proof_point"]

_STRUCTURE_PROMPT = """You are a messaging strategist. Given the source document below, extract and structure a complete Spec.

Return a JSON object matching this schema:
{
  "name": "Product or brand name",
  "summary": "2-3 sentence overview",
  "audience": "Target audience definition",
  "brand_personality": "Tone and voice descriptors",
  "positioning": "Core positioning statement",
  "tagline": "One punchy tagline (7 words or fewer)",
  "differentiation": "Key differentiators",
  "know_your_market": "Extract 'Know Your Market' fields if present (Vision, Audience, Before, After, etc.)",
  "pillars": [
    {
      "name": "Pillar name (1-4 words, e.g. Speed, Security, Scale)",
      "description": "One sentence summary of the pillar",
      "chunks": [
        {
          "section_type": "headline | benefit | use_case | proof_point | objection | social_proof | subhead",
          "priority": 1-5,
          "content": "Message content",
          "personas": [],
          "channels": ["all"],
          "addresses_pain_points": [],
          "resolves_objections": []
        }
      ]
    }
  ],
  "ungrouped_chunks": [
    {
      "section_type": "headline | benefit | use_case | proof_point | objection | social_proof | subhead",
      "priority": 1-5,
      "content": "Message content that doesn't fit in a pillar",
      "personas": [],
      "channels": ["all"],
      "addresses_pain_points": [],
      "resolves_objections": []
    }
  ],
  "personas": [
    {
      "name": "Persona name",
      "description": "Role description",
      "pain_points": [
        "They struggle with X",
        "Manual Y process wastes 3 days per week"
      ],
      "buying_triggers": [
        "Upcoming compliance audit",
        "Board mandate to reduce operational costs"
      ],
      "objections": [
        {
          "statement": "This is too expensive for our budget",
          "response": "Customers typically recover the cost in 6 months through a 40% reduction in operational overhead"
        },
        {
          "statement": "We already have a solution for this",
          "response": "Our customers find we complement existing tools by handling the workflow automation layer they lack"
        }
      ]
    }
  ],
  "missing_sections": []
}

Rules:
- Identify 3-5 main messaging pillars that organize the content (e.g., "Speed", "Security", "Scale", "Support")
- Group related key messages under their appropriate pillar
- Messages that don't fit a pillar go in "ungrouped_chunks"
- Map Umbrella Message Headline -> Tagline
- Map Value Pillars -> Benefits (but also create a pillar if distinct)
- Map Use Cases -> Use Case messages
- Map Proof Points -> Proof Point messages
- Map Objections -> Objection messages
- For each chunk, populate "addresses_pain_points" with the verbatim text of any pain
  point (from the personas list) that this message directly speaks to.
- Populate "resolves_objections" with the verbatim statement text of any objection this
  message helps overcome.
- Leave both arrays empty [] if the chunk is general and not specific to a pain/objection.

SOURCE DOCUMENT:
{content}
"""

_BRAND_GUIDE_PROMPT = """You are extracting brand and style guidelines from a document.

Return a JSON object matching this schema:
{
  "name": "Brand name or document title",
  "summary": "1-2 sentence overview of what this brand guide covers",
  "audience": "Internal teams this guide is intended for (e.g., marketing, content, design)",
  "positioning": "The brand's core positioning or mission statement if present",
  "tagline": "Official tagline or brand slogan if present",
  "differentiation": "What makes this brand's voice/style distinctive",
  "brand_personality": "Voice and tone descriptors extracted from the guide",
  "assertions": [
    {
      "section_type": "brand_voice | style_rule | word_list",
      "priority": 1-5,
      "content": "The guideline or rule text verbatim or closely paraphrased",
      "personas": [],
      "channels": ["all"]
    }
  ],
  "personas": [],
  "missing_sections": ["list any major sections you couldn't extract"]
}

Rules:
- Use section_type "brand_voice" for tone/personality descriptions
- Use section_type "style_rule" for specific writing rules (capitalization, punctuation, grammar)
- Use section_type "word_list" for approved/banned word lists
- Preserve exact wording for rules — do not paraphrase style_rule or word_list entries
- Set priority 1-2 for mandatory rules, 3-5 for guidance/suggestions

SOURCE DOCUMENT:
{content}
"""

_COMPETITIVE_BRIEF_PROMPT = """You are extracting competitive intelligence from a document.

Return a JSON object matching this schema:
{
  "name": "Competitor name or document title",
  "summary": "1-2 sentence summary of this competitive brief",
  "audience": "Sales, marketing, or product teams this brief is for",
  "positioning": "How we position against this competitor",
  "tagline": "Our differentiated tagline vs this competitor (if present)",
  "differentiation": "Our key advantages over this competitor",
  "brand_personality": "",
  "assertions": [
    {
      "section_type": "competitor_strength | competitor_weakness | competitive_response",
      "priority": 1-5,
      "content": "The intelligence or response message",
      "personas": [],
      "channels": ["all"]
    }
  ],
  "personas": [],
  "missing_sections": []
}

Rules:
- Use "competitor_strength" for things this competitor does well
- Use "competitor_weakness" for gaps, limitations, or vulnerabilities
- Use "competitive_response" for how we respond to this competitor's claims (our counter-messaging)
- Priority 1-2 for the most decisive competitive factors

SOURCE DOCUMENT:
{content}
"""

_CORP_NARRATIVE_PROMPT = """You are extracting a company's narrative, values, and founding story from a document.

Return a JSON object matching this schema:
{
  "name": "Company name",
  "summary": "1-2 sentence company overview",
  "audience": "Audiences this narrative is for (investors, employees, customers)",
  "positioning": "Core company positioning or mission statement",
  "tagline": "Company tagline or motto if present",
  "differentiation": "What makes this company's story distinct",
  "brand_personality": "Company personality and cultural values",
  "assertions": [
    {
      "section_type": "narrative_pillar | company_value | founding_story",
      "priority": 1-5,
      "content": "The narrative element",
      "personas": [],
      "channels": ["all"]
    }
  ],
  "personas": [],
  "missing_sections": []
}

Rules:
- Use "narrative_pillar" for the core strategic themes of the company story
- Use "company_value" for stated company values or cultural principles
- Use "founding_story" for origin story elements, key milestones, or the "why we exist" narrative

SOURCE DOCUMENT:
{content}
"""

_PERSONA_LIBRARY_PROMPT = """You are extracting buyer and user persona profiles from a document.

Return a JSON object matching this schema:
{
  "name": "Persona library name or document title",
  "summary": "Brief description of what personas are covered",
  "audience": "Teams these personas are for (sales, marketing, product)",
  "positioning": "",
  "tagline": "",
  "differentiation": "",
  "brand_personality": "",
  "assertions": [
    {
      "section_type": "persona_detail",
      "priority": 1-3,
      "content": "A specific insight about this persona — a key pain point, buying trigger, or objection in one sentence",
      "personas": ["<persona name>"],
      "channels": ["all"]
    }
  ],
  "personas": [
    {
      "name": "Role title (e.g., CISO, VP Sales)",
      "description": "Who they are and what they own",
      "pain_points": ["specific frustration 1", "..."],
      "buying_triggers": ["event or pressure that makes them evaluate", "..."],
      "objections": ["reason they hesitate to buy", "..."]
    }
  ],
  "missing_sections": []
}

Rules:
- Each persona should appear both as a full Persona object AND as assertions with section_type "persona_detail"
- assertions for personas should be atomic, quotable insights (one per message), not summaries
- Set priority 1 for the primary persona, 2-3 for secondary

SOURCE DOCUMENT:
{content}
"""

PERSONAS_JSON_PROMPT = """Extract all buyer personas from the markdown text below.
Return ONLY a valid JSON object with a "personas" array using this schema:
{{
  "personas": [
    {{
      "name": "persona name or role title",
      "description": "job title / who they are",
      "pain_points": ["specific pain point 1", "specific pain point 2"],
      "buying_triggers": ["trigger 1", "trigger 2"],
      "objections": ["objection 1", "objection 2"]
    }}
  ]
}}

If a field is empty return an empty array []. If there are no personas, return {{"personas": []}}.
Do not fabricate — only extract what is stated.

Markdown text:
{text}"""


class SpecStructurer:
    MAX_SINGLE_CHUNK = 24000
    CHUNK_SIZE = 20000
    CHUNK_OVERLAP = 1000

    _PROMPT_MAP = {
        "message_house": _STRUCTURE_PROMPT,
        "brand_guide": _BRAND_GUIDE_PROMPT,
        "competitive_brief": _COMPETITIVE_BRIEF_PROMPT,
        "corp_narrative": _CORP_NARRATIVE_PROMPT,
        "persona_library": _PERSONA_LIBRARY_PROMPT,
    }

    def __init__(self, openai_api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self._api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self._usage_lock = threading.Lock()
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self._api_key:
                raise ValueError("OpenAI API key required. Set OPENAI_API_KEY or pass openai_api_key.")
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def structure(self, text: str, source_name: str = "Untitled Source", document_type: str = "message_house") -> "tuple[StructuredSpec, dict]":
        """Run the structurer LLM on raw text and return (StructuredSpec, usage_dict).

        usage_dict has keys: input_tokens, output_tokens.
        For documents >24k chars, splits into overlapping chunks, structures each,
        then merges results.
        """
        self._usage: dict = {"input_tokens": 0, "output_tokens": 0}
        prompt_template = self._PROMPT_MAP.get(document_type, _STRUCTURE_PROMPT)

        if len(text) <= self.MAX_SINGLE_CHUNK:
            spec = self._structure_single_chunk(text, source_name, prompt_template)
        else:
            chunks = self._split_text(text)
            specs = [None] * len(chunks)
            max_workers = min(len(chunks), 5)  # cap at 5 to avoid rate-limit bursts
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {}
                for i, chunk in enumerate(chunks):
                    futures[pool.submit(self._structure_single_chunk, chunk, source_name, prompt_template)] = i
                for future in as_completed(futures):
                    specs[futures[future]] = future.result()
            spec = self._merge_structures(specs, source_name)
        return spec, dict(self._usage)

    def _split_text(self, text: str) -> list[str]:
        """Split text at paragraph boundaries into ~CHUNK_SIZE char chunks."""
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + self.CHUNK_SIZE
            if end >= len(text):
                chunks.append(text[start:])
                break
            # Walk back to nearest paragraph break
            split_at = text.rfind("\n\n", start, end)
            if split_at == -1 or split_at <= start:
                split_at = text.rfind("\n", start, end)
            if split_at == -1 or split_at <= start:
                split_at = end
            chunks.append(text[start:split_at])
            start = max(split_at - self.CHUNK_OVERLAP, split_at)
        return [c for c in chunks if c.strip()]

    def _structure_single_chunk(self, text: str, source_name: str, prompt_template: str) -> StructuredSpec:
        """Structure one text chunk with retry on transient OpenAI errors."""
        # Use replace instead of .format() so curly braces in the document don't
        # get interpreted as format placeholders (causes KeyError on e.g. JSON snippets).
        prompt = prompt_template.replace("{content}", text)
        raw = self._llm_call_with_retry(prompt, response_format={"type": "json_object"})
        try:
            data = json.loads(raw)
            # Ensure name is set if missing in LLM response
            if not data.get("name") or data["name"] in ("Product name", "Brand name", "Company name"):
                data["name"] = source_name
            return StructuredSpec(**data)
        except (json.JSONDecodeError, Exception) as e:
            # Fallback to markdown parser if JSON fails (though unlikely with response_format)
            log.warning("JSON parsing failed, falling back to markdown parser: %s", e)
            return self._parse_markdown(raw, source_name)

    def _llm_call_with_retry(self, prompt: str, max_retries: int = 3, response_format: dict = None) -> str:
        """Call the structuring LLM with exponential backoff on timeout/rate-limit."""
        delay = 2.0
        last_exc: Exception = RuntimeError("unreachable")
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a messaging strategist with deep B2B SaaS expertise. Extract real, high-signal messaging from source documents.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=4000,
                    timeout=90,
                    response_format=response_format,
                )
                if hasattr(self, "_usage") and response.usage:
                    with self._usage_lock:
                        self._usage["input_tokens"] += response.usage.prompt_tokens
                        self._usage["output_tokens"] += response.usage.completion_tokens
                return response.choices[0].message.content
            except (APITimeoutError, RateLimitError) as e:
                last_exc = e
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2
            except APIError:
                raise
        raise last_exc

    def _merge_structures(self, specs: list["StructuredSpec"], source_name: str) -> StructuredSpec:
        """Merge multiple StructuredSpec objects from chunked structuring."""
        if not specs:
            return StructuredSpec(name=source_name, summary="", audience="", brand_personality="",
                                   positioning="", tagline="", differentiation="", assertions=[], personas=[])
        if len(specs) == 1:
            return specs[0]

        def first_nonempty(attr: str) -> str:
            for h in specs:
                v = getattr(h, attr, "")
                if v and v.strip() and v.strip() != "[Not found in source]":
                    return v
            return ""

        merged_messages: list[dict] = []
        seen_content: set[str] = set()
        for h in specs:
            for m in h.assertions:
                key = m["content"].strip().lower()[:80]
                if key not in seen_content:
                    seen_content.add(key)
                    merged_messages.append(m)

        # Merge pillars (deduplicate by name; deduplicate chunks by content)
        pillar_by_name: dict[str, dict] = {}
        for h in specs:
            for pillar in h.pillars:
                pname = pillar.get("name", "")
                if pname not in pillar_by_name:
                    pillar_by_name[pname] = {"name": pname, "description": pillar.get("description", ""), "chunks": []}
                for chunk in pillar.get("chunks", []):
                    key = chunk.get("content", "").strip().lower()[:80]
                    if key and key not in seen_content:
                        seen_content.add(key)
                        pillar_by_name[pname]["chunks"].append(chunk)
        merged_pillars = list(pillar_by_name.values())

        # Merge ungrouped chunks (deduplicated against all pillar chunks too)
        merged_ungrouped: list[dict] = []
        for h in specs:
            for chunk in h.ungrouped_chunks:
                key = chunk.get("content", "").strip().lower()[:80]
                if key and key not in seen_content:
                    seen_content.add(key)
                    merged_ungrouped.append(chunk)

        merged_personas: list[dict] = []
        seen_names: set[str] = set()
        for h in specs:
            for p in h.personas:
                name_key = p.get("name", "").strip().lower()
                if name_key not in seen_names:
                    seen_names.add(name_key)
                    merged_personas.append(p)

        merged = StructuredSpec(
            name=first_nonempty("name") or source_name,
            summary=first_nonempty("summary"),
            audience=first_nonempty("audience"),
            brand_personality=first_nonempty("brand_personality"),
            positioning=first_nonempty("positioning"),
            tagline=first_nonempty("tagline"),
            differentiation=first_nonempty("differentiation"),
            assertions=merged_messages,
            pillars=merged_pillars,
            ungrouped_chunks=merged_ungrouped,
            personas=merged_personas,
            know_your_market=first_nonempty("know_your_market"),
        )
        merged.missing_sections = self._find_missing(merged)
        return merged

    def _parse_markdown(self, md: str, source_name: str) -> StructuredSpec:
        lines = md.split("\n")
        sections = {}
        current_section = None
        current_content = []

        for line in lines:
            stripped = line.strip()
            # Only split on ## headers — preserve ### sub-headers as content
            if stripped.startswith("## "):
                if current_section and current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = stripped[3:].strip().lower().replace(" ", "_")
                current_content = []
            elif current_section is not None:
                current_content.append(line)

        if current_section and current_content:
            sections[current_section] = "\n".join(current_content).strip()

        name = source_name
        for line in md.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                name = stripped[2:].strip()
                break

        # Heading text drives the section key. Accept both the historical
        # "## Key Messages" (used by every proxy file in data/sources/) and the
        # current "## Assertions" so existing documents keep parsing.
        assertions = self._parse_key_messages(
            sections.get("assertions") or sections.get("key_messages", "")
        )
        personas = self._parse_personas(sections.get("personas", ""))

        spec = StructuredSpec(
            name=name,
            summary=sections.get("summary", ""),
            audience=sections.get("target_audience", "") or sections.get("audience", ""),
            brand_personality=sections.get("brand_personality", ""),
            positioning=sections.get("positioning", ""),
            tagline=sections.get("tagline", ""),
            differentiation=sections.get("differentiation", ""),
            assertions=assertions,
            personas=personas,
            know_your_market=sections.get("know_your_market", ""),
        )
        spec.missing_sections = self._find_missing(spec)
        return spec

    def _find_missing(self, spec: "StructuredSpec") -> list[str]:
        missing = []
        field_map = {
            "summary": spec.summary,
            "audience": spec.audience,
            "brand_personality": spec.brand_personality,
            "positioning": spec.positioning,
            "tagline": spec.tagline,
            "differentiation": spec.differentiation,
        }
        for field, value in field_map.items():
            if not value or value.strip() in ("", "[Not found in source]"):
                missing.append(field)

        found_types = {m["section_type"] for m in spec.assertions}
        for t in REQUIRED_MESSAGE_TYPES:
            if t not in found_types:
                missing.append(f"messages:{t}")

        if not spec.personas:
            missing.append("personas")

        return missing

    def _parse_key_messages(self, text: str) -> list[dict]:
        messages = []
        section_map = {
            "headlines": ("headline", 1),
            "benefits": ("benefit", 1),
            "use_cases": ("use_case", 2),
            "proof_points": ("proof_point", 1),
            "objections": ("objection", 1),
            "subheads": ("subhead", 2),
            "social_proof": ("social_proof", 2),
        }

        current_section = None
        current_priority = 3

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("### "):
                raw_name = stripped[4:].strip().lower()
                raw_name = re.sub(r'\s*\([^)]*\)', '', raw_name).strip()
                section_name = raw_name.replace(" ", "_")
                current_section, current_priority = section_map.get(
                    section_name, (section_name, 3)
                )
                continue
            if stripped.startswith("-"):
                content = stripped[1:].strip()
                if content and content != "[Not found in source]":
                    messages.append(
                        {
                            "section_type": current_section or "positioning",
                            "priority": current_priority,
                            "content": content,
                            "variants": {},
                            "personas": [],
                            "channels": ["all"],
                        }
                    )

        return messages

    def _parse_personas(self, text: str) -> list[dict]:
        """Extract personas using LLM JSON output, falling back to regex parser."""
        if not text.strip():
            return []
        try:
            return self._extract_personas_json(text)
        except Exception:
            return self._parse_personas_regex(text)

    def _extract_personas_json(self, text: str) -> list[dict]:
        """Ask the LLM to return personas as structured JSON — no regex fragility."""
        prompt = PERSONAS_JSON_PROMPT.format(text=text)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You extract structured data from markdown text. Return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            timeout=30,
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        personas = data.get("personas", [])
        # Normalise — ensure all required keys exist
        result = []
        for p in personas:
            name = (p.get("name") or "").strip()
            if not name:
                continue
            result.append({
                "name": name,
                "description": (p.get("description") or "").strip(),
                "pain_points": [s for s in p.get("pain_points", []) if isinstance(s, str) and s.strip()],
                "buying_triggers": [s for s in p.get("buying_triggers", []) if isinstance(s, str) and s.strip()],
                "objections": [s for s in p.get("objections", []) if isinstance(s, str) and s.strip()],
            })
        return result

    def _parse_personas_regex(self, text: str) -> list[dict]:
        """Legacy regex-based persona parser — used as fallback only."""
        personas = []
        current: dict = {}

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                if current and "name" in current:
                    personas.append(current)
                    current = {}
                continue
            if stripped.startswith("### "):
                if current and "name" in current:
                    personas.append(current)
                    current = {}
                current["name"] = stripped[4:].strip()
                current["pain_points"] = []
                current["buying_triggers"] = []
                current["objections"] = []
                current["description"] = ""
                continue
            if "**Role:**" in stripped:
                current["description"] = stripped.split("**Role:**")[1].strip()
            elif "**Pain Points:**" in stripped:
                continue
            elif "**Buying Triggers:**" in stripped:
                continue
            elif "**Objections:**" in stripped:
                continue
            elif stripped.startswith("-"):
                content = stripped[1:].strip()
                if content == "[Not found in source]":
                    continue
                if "pain_points" not in current:
                    current["pain_points"] = []
                if current.get("description"):
                    current["pain_points"].append(content)
                elif "buying_triggers" not in current:
                    current["buying_triggers"] = [content]
                else:
                    current.setdefault("objections", []).append(content)

        if current and "name" in current:
            personas.append(current)

        return personas

    def to_markdown(self, spec: StructuredSpec) -> str:
        """Render a StructuredSpec back to markdown."""
        lines = [f"# {spec.name}", ""]
        if spec.know_your_market:
            lines.append(f"## Know Your Market\n{spec.know_your_market}")
        lines.append(f"## Summary\n{spec.summary}")
        lines.append(f"\n## Target Audience\n{spec.audience}")
        lines.append(f"\n## Brand Personality\n{spec.brand_personality}")
        lines.append(f"\n## Positioning\n{spec.positioning}")
        lines.append(f"\n## Tagline\n{spec.tagline}")
        lines.append(f"\n## Differentiation\n{spec.differentiation}")

        if spec.assertions:
            lines.append("\n## Key Messages")
            section_order = ["headline", "subhead", "benefit", "use_case", "proof_point", "objection", "social_proof"]
            from collections import defaultdict
            by_section = defaultdict(list)
            for m in spec.assertions:
                by_section[m["section_type"]].append(m)

            for sec in section_order:
                if sec in by_section:
                    lines.append(f"\n### {sec.title()}s")
                    for m in by_section[sec]:
                        lines.append(f"- {m['content']}")

        if spec.personas:
            lines.append("\n## Personas")
            for p in spec.personas:
                lines.append(f"\n### {p['name']}")
                if p.get("description"):
                    lines.append(f"**Role:** {p['description']}")
                if p.get("pain_points"):
                    lines.append("**Pain Points:** " + ", ".join(
                        i.get("content", str(i)) if isinstance(i, dict) else str(i)
                        for i in p["pain_points"]))
                if p.get("buying_triggers"):
                    lines.append("**Buying Triggers:** " + ", ".join(
                        i.get("content", str(i)) if isinstance(i, dict) else str(i)
                        for i in p["buying_triggers"]))
                if p.get("objections"):
                    lines.append("**Objections:** " + ", ".join(
                        i.get("statement", str(i)) if isinstance(i, dict) else str(i)
                        for i in p["objections"]))

        return "\n".join(lines)
