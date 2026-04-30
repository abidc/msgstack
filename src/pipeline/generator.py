"""Skill-based artifact generator using LLM + skills + grounding context."""

import os
from typing import Optional
from uuid import UUID

from openai import OpenAI
from pydantic import BaseModel

from src.models import MessageHouse, KeyMessage, Persona
from src.store import Store
from src.pipeline.skills import SkillManager


class ArtifactRequest(BaseModel):
    skill_id: str
    house_id: str
    context: dict = {}


class GeneratedArtifact(BaseModel):
    skill_id: str
    house_id: str
    house_name: str
    sections: dict
    raw_content: str
    grounded_messages: list[str]
    input_tokens: int = 0
    output_tokens: int = 0


class ArtifactGenerator:
    def __init__(
        self,
        store: Store,
        skills: SkillManager,
        openai_api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ):
        self.store = store
        self.skills = skills
        self.client = OpenAI(api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model

    def generate(self, skill_id: str, house_id: str, custom_context: dict = None) -> GeneratedArtifact:
        skill = self.skills.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")

        house = self.store.get_house(UUID(house_id))
        if not house:
            raise ValueError(f"House {house_id} not found")

        messages = self.store.get_key_messages(house.id)
        personas = self.store.get_personas(house.id)

        context = self._build_context(house, messages, personas, custom_context or {})
        skill_prompt = self.skills.fill_prompt(skill_id, context)

        # Always prepend the full structured grounding block so every artifact
        # has access to all section types, all personas, and all attributes —
        # regardless of which fields the skill template explicitly references.
        prompt = (
            "GROUNDING CONTEXT — every claim, headline, and proof point you write "
            "MUST be drawn from the material below. Do not introduce capabilities, "
            "statistics, or claims not present here.\n\n"
            f"{context['context']}\n\n"
            "---\n\n"
            f"TASK:\n{skill_prompt}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a marketing content generator. "
                        "You will be given a complete messaging framework including ALL section types "
                        "(headlines, subheads, benefits, proof points, objections, social proof, etc.), "
                        "ALL personas with their pain points, buying triggers, and objections, "
                        "and full brand positioning. "
                        "You MUST ground every claim, headline, and proof point in the provided framework. "
                        "Do not introduce product capabilities, statistics, or claims that are not present "
                        "in the provided context. Use the exact language, terminology, and tone from the "
                        "framework wherever possible. Output structured content that matches the skill's schema."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
        )

        raw = response.choices[0].message.content
        sections = self._parse_sections(raw, skill)
        grounded = [m.content for m in messages]

        return GeneratedArtifact(
            skill_id=skill_id,
            house_id=house_id,
            house_name=house.name,
            sections=sections,
            raw_content=raw,
            grounded_messages=grounded,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

    def _build_context(
        self,
        house: MessageHouse,
        messages: list[KeyMessage],
        personas: list[Persona],
        custom: dict,
    ) -> dict:
        # Group ALL messages by section type, sorted by priority within each group
        by_section: dict[str, list[KeyMessage]] = {}
        for m in messages:
            key = str(m.section_type)
            by_section.setdefault(key, []).append(m)

        section_blocks = []
        for section_type in sorted(by_section):
            msgs = sorted(by_section[section_type], key=lambda x: x.priority or 3)
            section_blocks.append(f"### {section_type.upper().replace('_', ' ')} ({len(msgs)})")
            for m in msgs:
                section_blocks.append(f"  - {m.content}")
        key_messages_str = "\n".join(section_blocks)

        # Build full persona blocks — all personas, all attributes
        persona_blocks = []
        for p in personas:
            lines = [f"**{p.name}**"]
            if p.description:
                lines.append(f"  Description: {p.description}")
            pain = p.pain_points or []
            if pain:
                lines.append(f"  Pain Points: {'; '.join(str(x) for x in pain)}")
            triggers = p.buying_triggers or []
            if triggers:
                lines.append(f"  Buying Triggers: {'; '.join(str(x) for x in triggers)}")
            objs = p.objections or []
            if objs:
                obj_strs = [
                    ob.get("statement", str(ob)) if isinstance(ob, dict) else str(ob)
                    for ob in objs
                ]
                lines.append(f"  Objections: {'; '.join(obj_strs)}")
            persona_blocks.append("\n".join(lines))
        personas_str = "\n\n".join(persona_blocks)

        context_block = (
            f"## {house.name}\n\n"
            f"**Positioning:** {house.positioning or '(not set)'}\n"
            f"**Tagline:** {house.tagline or '(not set)'}\n"
            f"**Differentiation:** {house.differentiation or '(not set)'}\n"
            f"**Audience:** {house.audience or '(not set)'}\n"
            f"**Brand Personality:** {house.brand_personality or '(not set)'}\n\n"
            f"## Key Messages ({len(messages)} total, all sections)\n\n"
            f"{key_messages_str}\n\n"
            f"## Personas ({len(personas)} total)\n\n"
            f"{personas_str}"
        )

        # Safe single-item values for skill templates that reference {persona} / {objections}
        first_persona = personas[0] if personas else None
        first_obj_list: list[str] = []
        if first_persona:
            for ob in (first_persona.objections or []):
                first_obj_list.append(
                    ob.get("statement", str(ob)) if isinstance(ob, dict) else str(ob)
                )

        context = {
            "house_name": house.name,
            "positioning": house.positioning or "",
            "tagline": house.tagline or "",
            "differentiation": house.differentiation or "",
            "audience": house.audience or "",
            "brand_personality": house.brand_personality or "",
            "key_messages": key_messages_str,
            "personas_detail": personas_str,
            "context": context_block,
            "primary_message": messages[0].content if messages else "",
            "persona": first_persona.name if first_persona else "",
            "objections": "; ".join(first_obj_list) if first_obj_list else "",
            # defaults for optional context variables used in some skill templates
            "target_length": "800-1200",
            "tone": "professional",
            "event_name": "the event",
        }
        context.update(custom)
        return context

    def _parse_sections(self, raw: str, skill: dict) -> dict:
        sections = {}
        section_keys = {s["key"] for s in skill.get("sections", [])}

        current_key = None
        current_lines = []

        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue

            for key in section_keys:
                if line.lower().startswith(key.lower() + ":") or line.lower().startswith(f"**{key}**"):
                    if current_key:
                        sections[current_key] = "\n".join(current_lines).strip()
                    current_key = key
                    current_lines = [line.split(":", 1)[1].strip() if ":" in line else line]
                    break
            else:
                if current_key:
                    current_lines.append(line)

        if current_key:
            sections[current_key] = "\n".join(current_lines).strip()

        for key in section_keys:
            if key not in sections and key in raw.lower():
                import re

                match = re.search(
                    rf"{key}[:\s]+(.+?)(?=\n\n|\n[A-Z]|$)", raw, re.IGNORECASE | re.DOTALL
                )
                if match:
                    sections[key] = match.group(1).strip()

        return sections
