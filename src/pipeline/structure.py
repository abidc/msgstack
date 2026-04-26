"""LLM-based MessageHouse structuring: raw text → structured markdown."""

import os
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, Field


class StructuredHouse(BaseModel):
    name: str
    summary: str
    audience: str
    brand_personality: str
    positioning: str
    tagline: str
    differentiation: str
    key_messages: list[dict]
    personas: list[dict]
    missing_sections: list[str] = Field(default_factory=list)

REQUIRED_SECTIONS = ["summary", "audience", "brand_personality", "positioning", "tagline", "differentiation"]
REQUIRED_MESSAGE_TYPES = ["headline", "benefit", "proof_point", "objection"]


STRUCTURER_PROMPT = """You are a messaging strategist. Given the source document below, extract and structure a complete MessageHouse in markdown format.

Follow this EXACT structure:

```markdown
# {Name}

## Summary
{2-3 sentence overview of the product/solution}

## Target Audience
{Who this is for — persona name, role, company size, key characteristics}

## Brand Personality
{Tone, voice, word choices — what the brand sounds like}

## Positioning
{The core positioning statement — what it is, who it's for, why it's different}

## Tagline
{One punchy tagline (7 words or fewer)}

## Differentiation
{What sets this apart from competitors in 2-3 key ways}

## Key Messages

### Headlines (Priority 1-2)
- {Strong headline copy}

### Benefits (Priority 1-3)
- {Benefit statement}

### Proof Points (Priority 1-2)
- {Social proof, stats, customer evidence}

### Objections (Priority 1-2)
- {Common objections + rebuttal}

## Personas

### {Persona Name}
**Role:** {Their job title}
**Pain Points:** {What frustrates them}
**Buying Triggers:** {What makes them buy}
**Objections:** {What stops them}
```

Rules:
- Extract REAL content from the document. Do not invent messaging.
- Headlines: benefit-led, specific, credible
- Benefits: lead with outcomes, not features
- Proof points: pull actual stats/quotes from the document when present
- If information is missing, mark as "[Not found in source]" — do not fabricate
- Prioritize the most compelling, high-signal content

SOURCE DOCUMENT:
{content}
"""


class HouseStructurer:
    def __init__(self, openai_api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model

    def structure(self, text: str, source_name: str = "Untitled Source") -> StructuredHouse:
        """Run the structurer LLM on raw text and return a StructuredHouse."""
        prompt = STRUCTURER_PROMPT.format(content=text[:24000])

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
        )

        raw = response.choices[0].message.content
        return self._parse_markdown(raw, source_name)

    def _parse_markdown(self, md: str, source_name: str) -> StructuredHouse:
        lines = md.split("\n")
        sections = {}
        current_section = None
        current_content = []

        for line in lines:
            stripped = line.strip()
            # Only split on ## headers — preserve ### sub-headers as content
            # so that _parse_key_messages receives the full block including subsections
            if stripped.startswith("## "):
                if current_section and current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = stripped[3:].strip().lower().replace(" ", "_")
                current_content = []
            elif current_section is not None:
                current_content.append(line)  # preserve original line (including ###)

        if current_section and current_content:
            sections[current_section] = "\n".join(current_content).strip()

        name = source_name
        for line in md.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                name = stripped[2:].strip()
                break

        key_messages = self._parse_key_messages(sections.get("key_messages", ""))
        personas = self._parse_personas(sections.get("personas", ""))

        house = StructuredHouse(
            name=name,
            summary=sections.get("summary", ""),
            audience=sections.get("target_audience", "") or sections.get("audience", ""),
            brand_personality=sections.get("brand_personality", ""),
            positioning=sections.get("positioning", ""),
            tagline=sections.get("tagline", ""),
            differentiation=sections.get("differentiation", ""),
            key_messages=key_messages,
            personas=personas,
        )
        house.missing_sections = self._find_missing(house)
        return house

    def _find_missing(self, house: "StructuredHouse") -> list[str]:
        missing = []
        field_map = {
            "summary": house.summary,
            "audience": house.audience,
            "brand_personality": house.brand_personality,
            "positioning": house.positioning,
            "tagline": house.tagline,
            "differentiation": house.differentiation,
        }
        for field, value in field_map.items():
            if not value or value.strip() in ("", "[Not found in source]"):
                missing.append(field)

        found_types = {m["section_type"] for m in house.key_messages}
        for t in REQUIRED_MESSAGE_TYPES:
            if t not in found_types:
                missing.append(f"messages:{t}")

        if not house.personas:
            missing.append("personas")

        return missing

    def _parse_key_messages(self, text: str) -> list[dict]:
        messages = []
        section_map = {
            "headlines": ("headline", 1),
            "benefits": ("benefit", 1),
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
                section_name = stripped[4:].strip().lower().replace(" ", "_")
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
        personas = []
        current = {}

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

    def to_markdown(self, house: StructuredHouse) -> str:
        """Render a StructuredHouse back to markdown."""
        lines = [f"# {house.name}", ""]
        lines.append(f"## Summary\n{house.summary}")
        lines.append(f"\n## Target Audience\n{house.audience}")
        lines.append(f"\n## Brand Personality\n{house.brand_personality}")
        lines.append(f"\n## Positioning\n{house.positioning}")
        lines.append(f"\n## Tagline\n{house.tagline}")
        lines.append(f"\n## Differentiation\n{house.differentiation}")

        if house.key_messages:
            lines.append("\n## Key Messages")
            section_order = ["headline", "subhead", "benefit", "proof_point", "objection", "social_proof"]
            from collections import defaultdict
            by_section = defaultdict(list)
            for m in house.key_messages:
                by_section[m["section_type"]].append(m)

            for sec in section_order:
                if sec in by_section:
                    lines.append(f"\n### {sec.title()}s")
                    for m in by_section[sec]:
                        lines.append(f"- {m['content']}")

        if house.personas:
            lines.append("\n## Personas")
            for p in house.personas:
                lines.append(f"\n### {p['name']}")
                if p.get("description"):
                    lines.append(f"**Role:** {p['description']}")
                if p.get("pain_points"):
                    lines.append("**Pain Points:** " + ", ".join(p["pain_points"]))
                if p.get("buying_triggers"):
                    lines.append("**Buying Triggers:** " + ", ".join(p["buying_triggers"]))
                if p.get("objections"):
                    lines.append("**Objections:** " + ", ".join(p["objections"]))

        return "\n".join(lines)