"""Skill-based artifact generator using LLM + skills + grounding context."""

import json
import os
from typing import Optional
from uuid import UUID

from openai import OpenAI
from pydantic import BaseModel

from src.models import MessageHouse, KeyMessage, Persona
from src.store import Store
from src.pipeline.skills import SkillManager
from src.design.validators import DesignSpec, validate_and_fill_design_spec
from src.rendering.renderer import get_renderer, RenderOutput


class ArtifactRequest(BaseModel):
    skill_id: str
    house_id: str
    context: dict = {}


class GeneratedArtifact(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    skill_id: str
    house_id: str
    house_name: str
    sections: dict
    raw_content: str
    grounded_messages: list[str]
    input_tokens: int = 0
    output_tokens: int = 0
    design_spec: Optional[dict] = None
    renderer_type: Optional[str] = None
    renderer_output: Optional[RenderOutput] = None


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

        # Check if this is a visual artifact type
        artifact_type = skill.get("prefab_template") or skill_id
        is_visual = artifact_type in ("one_pager_visual", "datasheet", "battlecard_visual")

        context = self._build_context(house, messages, personas, custom_context or {})

        # For visual artifacts, pre-fill template zones before LLM call
        visual_context = None
        template = None
        if is_visual:
            template = self._get_template(artifact_type)
            if template:
                visual_context = self._build_visual_context(
                    house_id, template, artifact_type, house, messages, personas
                )
                context["visual_context"] = visual_context
                context["template_zones"] = template.get("zones", [])

        skill_prompt = self.skills.fill_prompt(skill_id, context)

        # Inject template + pre-filled context into LLM prompt for visual artifacts
        if is_visual and visual_context:
            zone_hint = json.dumps(visual_context.get("zone_mapping", {}), indent=2)
            prompt = (
                f"TEMPLATE ZONES (pre-filled with approved content):\n{zone_hint}\n\n"
                f"TASK:\n{skill_prompt}\n\n"
                "INSTRUCTIONS:\n"
                "- Copy the pre-filled content EXACTLY into the correct zones.\n"
                "- Your job is copy-editing and tone-polishing, NOT data organization.\n"
                "- Do NOT invent new content. Use only what is pre-filled.\n"
                "- Output ONLY the design_spec JSON."
            )
        else:
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

        # For visual artifacts, validate and save design_spec
        if is_visual and template:
            try:
                design_spec = validate_and_fill_design_spec(
                    raw, template.get("zones", []), context, template.get("page_spec")
                )
                sections["design_spec"] = design_spec.model_dump()
            except Exception as e:
                # Fallback: inject template defaults
                sections["design_spec"] = self._fallback_design_spec(
                    template, context, visual_context
                )

        # Renderer routing: check skill's renderer field and route to appropriate renderer
        renderer_type = skill.get("renderer", "html")
        renderer = get_renderer(renderer_type)
        render_output = None
        
        # Get house_name for context
        render_context = {"house_name": house.name}
        render_context.update(context)
        
        if renderer_type == "html":
            render_output = renderer.render_html(sections, render_context)
        elif renderer_type == "fabric":
            render_output = renderer.render_fabric(sections, render_context)
        elif renderer_type == "reveal":
            render_output = renderer.render_reveal(sections, render_context)
        elif renderer_type == "penpot":
            render_output = renderer.render_penpot(sections, render_context)

        return GeneratedArtifact(
            skill_id=skill_id,
            house_id=house_id,
            house_name=house.name,
            sections=sections,
            raw_content=raw,
            grounded_messages=grounded,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            design_spec=sections.get("design_spec"),
            renderer_type=renderer_type,
            renderer_output=render_output,
        )

    def _get_template(self, artifact_type: str) -> Optional[dict]:
        """Load template for the given artifact type via TemplateRegistry."""
        try:
            from src.design.template_registry import TemplateRegistry
            registry = TemplateRegistry()
            norm_type = artifact_type
            if norm_type == "one_pager_visual":
                norm_type = "datasheet"
            elif norm_type == "battlecard_visual":
                norm_type = "battlecard"
            
            template = registry.get_template(norm_type)
            if template:
                data = template.model_dump()
                data["id"] = template.artifact_type
                return data
        except Exception as e:
            log.warning("Failed to load template %s: %s", artifact_type, e)
        return None

    def _build_visual_context(
        self,
        house_id: str,
        template: dict,
        artifact_type: str,
        house: MessageHouse,
        messages: list[KeyMessage],
        personas: list[Persona],
    ) -> dict:
        """
        Pre-assign messaging house content to template zones BEFORE the LLM call.
        Maps:
        - tagline → hero.text_content
        - positioning → hero.body
        - differentiation → pillar_grid
        - top 6 key messages by priority → message_list
        - personas → persona_strip (max 3, primary first)
        - proof points → proof_block (max 3)
        """
        zone_mapping = {}

        # Build message lookup by section type
        by_section = {}
        for m in messages:
            key = str(m.section_type)
            by_section.setdefault(key, []).append(m)

        # Sort each section by priority
        for section_type in by_section:
            by_section[section_type].sort(key=lambda x: x.priority or 3)

        # Get template zones
        template_zones = template.get("zones", [])

        for zone in template_zones:
            zone_id = zone.get("id", "")
            zone_type = zone.get("type", "")
            capacity = zone.get("capacity", 3)
            max_chars = zone.get("max_chars", 500)

            content = {"text": "", "items": []}

            if zone_type == "hero":
                # Map tagline → hero.text_content
                if house.tagline:
                    content["text"] = house.tagline[:max_chars]
                # Also map positioning → hero.body if there's a body sub-zone
                if zone_id.endswith("_body") and house.positioning:
                    content["text"] = house.positioning[:max_chars]

            elif zone_type == "positioning":
                if house.positioning:
                    content["text"] = house.positioning[:max_chars]

            elif zone_type == "pillar_grid" or zone_type == "differentiation":
                # Map differentiation → pillar_grid
                if house.differentiation:
                    items = [item.strip() for item in house.differentiation.split(".") if item.strip()][:capacity]
                    content["items"] = items

            elif zone_type == "message_list":
                # Top 6 key messages by priority
                all_msgs = []
                for section_msgs in by_section.values():
                    all_msgs.extend(section_msgs)
                all_msgs.sort(key=lambda x: x.priority or 3)
                content["items"] = [m.content[:max_chars] for m in all_msgs[:capacity * 2][:6]]

            elif zone_type == "persona_strip":
                # Persona truncation: max 3 personas, primary first, then by completeness
                sorted_personas = sorted(
                    personas,
                    key=lambda p: (0 if getattr(p, 'is_primary', False) else 1, -len(p.description or ""))
                )[:3]
                content["items"] = [p.name for p in sorted_personas]

            elif zone_type == "proof_block":
                # Proof points → proof_block (max 3)
                proof_msgs = by_section.get("proof_point", [])
                content["items"] = [m.content[:max_chars] for m in proof_msgs[:capacity]][:3]

            elif zone_type == "benefit_list":
                benefit_msgs = by_section.get("benefit", [])
                content["items"] = [m.content[:max_chars] for m in benefit_msgs[:capacity]]

            elif zone_type == "objection_list" and artifact_type == "battlecard_visual":
                # Pull objections + responses from graph for verbatim accuracy
                objection_items = []
                for p in personas:
                    objs = p.objections or []
                    for ob in objs[:capacity - len(objection_items)]:
                        if isinstance(ob, dict):
                            objection_items.append(ob.get("statement", str(ob)))
                        else:
                            objection_items.append(str(ob))
                    if len(objection_items) >= capacity:
                        break
                content["items"] = objection_items[:capacity]

            zone_mapping[zone_id] = {
                "type": zone_type,
                "content": content,
                "capacity": capacity,
                "max_chars": max_chars,
            }

        return {
            "zone_mapping": zone_mapping,
            "template_id": template.get("id", artifact_type),
            "artifact_type": artifact_type,
        }

    def _fallback_design_spec(self, template: dict, context: dict, visual_context: dict | None) -> dict:
        """Generate fallback design spec with template defaults."""
        zones = []
        template_zones = template.get("zones", [])

        for tz in template_zones:
            # Copy all fields from template zone
            zone = dict(tz)

            # Try to get pre-filled content from visual context
            if visual_context and "zone_mapping" in visual_context:
                vm = visual_context["zone_mapping"].get(tz.get("id"))
                if vm and "content" in vm:
                    cnt = vm["content"]
                    if "text" in cnt and cnt["text"] and not zone.get("text_content"):
                        zone["text_content"] = cnt["text"]
                    if "items" in cnt and cnt["items"] and not zone.get("list_items"):
                        zone["list_items"] = cnt["items"]

            zones.append(zone)

        return {
            "version": "2.0",
            "artifact_type": template.get("artifact_type", "unknown"),
            "template_id": template.get("id", ""),
            "zones": zones,
            "page_settings": template.get("page_spec", {
                "width": 850,
                "height": 1100,
                "grid_cols": 12,
                "gutter": 20,
                "margin": 40
            }),
        }

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
