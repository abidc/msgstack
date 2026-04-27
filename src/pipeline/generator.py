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
        prompt = self.skills.fill_prompt(skill_id, context)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a marketing content generator. Generate artifacts based on the provided prompt and context. Output structured content that matches the skill's schema.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
        )

        raw = response.choices[0].message.content
        sections = self._parse_sections(raw, skill)
        grounded = [m.content for m in messages[:5]]

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
        key_messages_str = "\n".join(
            f"- {str(m.section_type)}: {m.content}" for m in messages[:10]
        )
        persona_names = ", ".join(p.name for p in personas[:3])
        context_block = (
            f"Positioning: {house.positioning}\n"
            f"Tagline: {house.tagline}\n"
            f"Differentiation: {house.differentiation}\n"
            f"Audience: {house.audience}\n"
            f"Brand personality: {house.brand_personality}\n"
            f"Personas: {persona_names}\n"
            f"Key messages:\n{key_messages_str}"
        )
        context = {
            "house_name": house.name,
            "positioning": house.positioning,
            "tagline": house.tagline,
            "differentiation": house.differentiation,
            "audience": house.audience,
            "key_messages": key_messages_str,
            "context": context_block,
            "primary_message": messages[0].content if messages else "",
            "persona": personas[0].name if personas else "",
            "objections": ", ".join(personas[0].objections[:3]) if personas and personas[0].objections else "",
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
