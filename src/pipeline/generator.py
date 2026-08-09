"""Skill-based artifact generator using LLM + skills + grounding context."""

import json
import logging
import os
import re
from typing import Optional
from uuid import UUID

log = logging.getLogger(__name__)

# Per-entry tier directives injected into the grounding block (spec §4.9).
# Tier 3 and untier'd entries carry no directive — default latitude.
TIER_DIRECTIVES = {
    "tier_1_locked": "[TIER 1 — LOCKED: reproduce this text VERBATIM wherever used. Do not paraphrase, summarize, or alter.] ",
    "tier_2_structured": "[TIER 2 — preserve substance and positioning; phrasing may adapt.] ",
}

TIER_CONTRACT_PREAMBLE = (
    "CONTENT TIER CONTRACT: entries tagged [TIER 1 — LOCKED] are sacrosanct — copy them "
    "word-for-word wherever their content is used; never paraphrase, shorten, or restyle them. "
    "Entries tagged [TIER 2] must keep their substance and positioning intact, though phrasing "
    "may adapt. Untagged entries may be adapted freely within the brand voice.\n\n"
)

from openai import OpenAI
from pydantic import BaseModel

from src.models import Spec, Assertion, Audience
from src.store import Store
from src.pipeline.skills import SkillManager
from src.design.validators import DesignSpec, validate_and_fill_design_spec
from src.rendering.renderer import get_renderer, RenderOutput


class ArtifactRequest(BaseModel):
    skill_id: str
    spec_id: str
    context: dict = {}


class GeneratedArtifact(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    skill_id: str
    spec_id: str
    spec_name: str
    sections: dict
    raw_content: str
    grounded_messages: list[str]
    input_tokens: int = 0
    output_tokens: int = 0
    design_spec: Optional[dict] = None
    renderer_type: Optional[str] = None
    renderer_output: Optional[RenderOutput] = None
    used_drafts_fallback: bool = False
    tier_violations: list[dict] = []


def _normalize_ws(text: str) -> str:
    """Collapse whitespace so formatting differences don't fail a verbatim check."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def find_tier1_violations(messages: list, output: str) -> list[dict]:
    """Detect Tier 1 entries that appear to have been used but not verbatim.

    An entry counts as "used" when most of its significant words appear in the
    output (fuzzy match); it passes when its whitespace-normalized text appears
    as an exact substring. Used-but-not-verbatim → violation.
    """
    violations = []
    norm_output = _normalize_ws(output)
    output_words = set(re.findall(r"[a-z0-9']+", norm_output))
    for m in messages:
        if (getattr(m, "content_tier", None) or "") != "tier_1_locked":
            continue
        norm_entry = _normalize_ws(m.content)
        if not norm_entry:
            continue
        if norm_entry in norm_output:
            continue  # verbatim — OK
        entry_words = [w for w in re.findall(r"[a-z0-9']+", norm_entry) if len(w) > 3]
        if not entry_words:
            continue
        overlap = sum(1 for w in entry_words if w in output_words) / len(entry_words)
        if overlap >= 0.6:
            violations.append({
                "entry_id": str(getattr(m, "id", "")),
                "content": m.content,
                "word_overlap": round(overlap, 2),
                "warning": "Tier 1 entry appears to have been paraphrased — it must be reproduced verbatim.",
            })
    return violations


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
        from src.config import llm_client
        self.client = llm_client(openai_api_key)
        self.model = model

    def generate(self, skill_id: str, spec_id: str, custom_context: dict = None) -> GeneratedArtifact:
        skill = self.skills.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")

        spec = self.store.get_spec(UUID(spec_id))
        if not spec:
            raise ValueError(f"Spec {spec_id} not found")

        messages = self.store.get_key_messages(spec.id, include_unapproved=True)
        # Approval gating: skip non-Approved messages by default, unless include_drafts is true
        include_drafts = False
        if custom_context and (custom_context.get("include_drafts") in (True, "true", "1", 1)):
            include_drafts = True

        approved_messages = [m for m in messages if m.status == "approved"]
        used_drafts_fallback = False

        if include_drafts:
            messages_to_use = messages
        elif approved_messages:
            messages_to_use = approved_messages
        else:
            # Fallback to drafts/in_review if no approved messages exist
            messages_to_use = [m for m in messages if m.status in ("draft", "in_review")]
            used_drafts_fallback = len(messages_to_use) > 0

        messages = messages_to_use

        audiences = self.store.get_audiences(spec.id)

        # Check if this is a visual artifact type
        artifact_type = skill.get("prefab_template") or skill_id
        is_visual = skill.get("renderer") == "fabric"

        context = self._build_context(spec, messages, audiences, custom_context or {})

        # Tonal sliders mapping:
        tone_register = ""
        if custom_context:
            professionalism = custom_context.get("tone_professionalism", 0.5)
            warmth = custom_context.get("tone_warmth", 0.5)
            # Map float sliders to specific prompt instructions
            tone_register = (
                f"\nTONE & REGISTER BOUNDS:\n"
                f"- Professionalism level: {professionalism} (1.0 = highly formal, 0.0 = highly casual)\n"
                f"- Warmth level: {warmth} (1.0 = highly friendly, 0.0 = highly objective and technical)\n"
                f"Adjust output register to match these bounds while respecting brand personality."
            )

        # For visual artifacts, pre-fill template zones before LLM call
        visual_context = None
        template = None
        if is_visual:
            template = self._get_template(artifact_type)
            if template:
                visual_context = self._build_visual_context(
                    spec_id, template, artifact_type, spec, messages, audiences
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
            # has access to all section types, all audiences, and all attributes —
            # regardless of which fields the skill template explicitly references.
            prompt = (
                "GROUNDING CONTEXT — every claim, headline, and proof point you write "
                "MUST be drawn from the material below. Do not introduce capabilities, "
                "statistics, or claims not present here.\n\n"
                f"{TIER_CONTRACT_PREAMBLE}"
                f"{context['context']}\n"
                f"{tone_register}\n\n"
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
                        "(headlines, subheads, benefits, proof points, qa_pairs, social proof, etc.), "
                        "ALL audiences with their pain points, buying triggers, and qa_pairs, "
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
        
        try:
            from src.pipeline.vocabulary import apply_controlled_vocabulary
            raw = apply_controlled_vocabulary(raw, spec.id, self.store)
            # Re-parse sections after sweeping
            sections = self._parse_sections(raw, skill)
        except Exception as e:
            log.error(f"Vocabulary filtering failed: {e}")
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
        elif skill.get("renderer") == "reveal":
            try:
                import re
                json_match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
                json_str = json_match.group(1) if json_match else raw
                start_idx = json_str.find("{")
                end_idx = json_str.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    sections["design_spec"] = json.loads(json_str[start_idx:end_idx+1])
            except Exception as e:
                log.error(f"Failed to parse reveal JSON: {e}")
                sections["design_spec"] = {"slides": []}

        # Renderer routing: check skill's renderer field and route to appropriate renderer
        renderer_type = skill.get("renderer", "html")
        renderer = get_renderer(renderer_type)
        render_output = None
        
        # Get spec_name for context
        render_context = {"spec_name": spec.name}
        render_context.update(context)
        
        if renderer_type == "html":
            render_output = renderer.render_html(sections, render_context)
        elif renderer_type == "fabric":
            render_output = renderer.render_fabric(sections, render_context)
        elif renderer_type == "reveal":
            render_output = renderer.render_reveal(sections, render_context)
        elif renderer_type == "penpot":
            render_output = renderer.render_penpot(sections, render_context)

        tier_violations = find_tier1_violations(messages, raw)
        if tier_violations:
            log.warning(
                "Artifact %s/%s has %d Tier 1 verbatim violation(s)",
                skill_id, spec_id, len(tier_violations),
            )

        return GeneratedArtifact(
            skill_id=skill_id,
            spec_id=spec_id,
            spec_name=spec.name,
            sections=sections,
            raw_content=raw,
            grounded_messages=grounded,
            tier_violations=tier_violations,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            design_spec=sections.get("design_spec"),
            renderer_type=renderer_type,
            renderer_output=render_output,
            used_drafts_fallback=used_drafts_fallback,
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
        spec_id: str,
        template: dict,
        artifact_type: str,
        spec: Spec,
        messages: list[Assertion],
        audiences: list[Audience],
    ) -> dict:
        """
        Pre-assign messaging spec content to template zones BEFORE the LLM call.
        Maps:
        - tagline → hero.text_content
        - positioning → hero.body
        - differentiation → pillar_grid
        - top 6 key messages by priority → message_list
        - audiences → audience_strip (max 3, primary first)
        - proof points → proof_block (max 3)
        """
        zone_mapping = {}

        # Build message lookup by section type
        by_section = {}
        for m in messages:
            key = str(m.assertion_type)
            by_section.setdefault(key, []).append(m)

        # Sort each section by priority
        for assertion_type in by_section:
            by_section[assertion_type].sort(key=lambda x: x.priority or 3)

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
                if spec.tagline:
                    content["text"] = spec.tagline[:max_chars]
                # Also map positioning → hero.body if there's a body sub-zone
                if zone_id.endswith("_body") and spec.positioning:
                    content["text"] = spec.positioning[:max_chars]

            elif zone_type == "positioning":
                if spec.positioning:
                    content["text"] = spec.positioning[:max_chars]

            elif zone_type == "pillar_grid" or zone_type == "differentiation":
                # Map differentiation → pillar_grid
                if spec.differentiation:
                    items = [item.strip() for item in spec.differentiation.split(".") if item.strip()][:capacity]
                    content["items"] = items

            elif zone_type == "message_list":
                # Top 6 key messages by priority
                all_msgs = []
                for section_msgs in by_section.values():
                    all_msgs.extend(section_msgs)
                all_msgs.sort(key=lambda x: x.priority or 3)
                content["items"] = [m.content[:max_chars] for m in all_msgs[:capacity * 2][:6]]

            elif zone_type == "audience_strip":
                # Audience truncation: max 3 audiences, primary first, then by completeness
                sorted_audiences = sorted(
                    audiences,
                    key=lambda p: (0 if getattr(p, 'is_primary', False) else 1, -len(p.description or ""))
                )[:3]
                content["items"] = [p.name for p in sorted_audiences]

            elif zone_type == "proof_block":
                # Proof points → proof_block (max 3)
                proof_msgs = by_section.get("proof_point", [])
                content["items"] = [m.content[:max_chars] for m in proof_msgs[:capacity]][:3]

            elif zone_type == "benefit_list":
                benefit_msgs = by_section.get("benefit", [])
                content["items"] = [m.content[:max_chars] for m in benefit_msgs[:capacity]]

            elif zone_type == "qa_pair_list" and artifact_type == "battlecard_visual":
                # Pull qa_pairs + responses from graph for verbatim accuracy
                qa_pair_items = []
                for p in audiences:
                    objs = p.qa_pairs or []
                    for ob in objs[:capacity - len(qa_pair_items)]:
                        if isinstance(ob, dict):
                            qa_pair_items.append(ob.get("statement", str(ob)))
                        else:
                            qa_pair_items.append(str(ob))
                    if len(qa_pair_items) >= capacity:
                        break
                content["items"] = qa_pair_items[:capacity]

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
        spec: Spec,
        messages: list[Assertion],
        audiences: list[Audience],
        custom: dict,
    ) -> dict:
        # Tier affects ordering and annotation ONLY — never inclusion. Untier'd
        # (legacy NULL-tier) entries are always included, sorted after tiered ones.
        # Unset tier blocks *promotion* (update_entry_status), not generation.
        tier_order = {"tier_1_locked": 0, "tier_2_structured": 1, "tier_3_grounded": 2}
        # Group ALL messages by section type, sorted by tier then priority within each group
        by_section: dict[str, list[Assertion]] = {}
        for m in messages:
            key = str(m.assertion_type)
            by_section.setdefault(key, []).append(m)

        section_blocks = []
        for assertion_type in sorted(by_section):
            msgs = sorted(by_section[assertion_type], key=lambda x: (tier_order.get(getattr(x, "content_tier", None) or "", 99), x.priority or 3))
            section_blocks.append(f"### {assertion_type.upper().replace('_', ' ')} ({len(msgs)})")
            for m in msgs:
                directive = TIER_DIRECTIVES.get(getattr(m, "content_tier", None) or "", "")
                section_blocks.append(f"  - {directive}{m.content}")
        key_messages_str = "\n".join(section_blocks)

        # Build full audience blocks — all audiences, all attributes
        audience_blocks = []
        for p in audiences:
            lines = [f"**{p.name}**"]
            if p.description:
                lines.append(f"  Description: {p.description}")
            pain = p.qa_pairs or []
            if pain:
                lines.append(f"  Pain Points: {'; '.join(str(x) for x in pain)}")
            triggers = []
            if triggers:
                lines.append(f"  Buying Triggers: {'; '.join(str(x) for x in triggers)}")
            objs = p.qa_pairs or []
            if objs:
                obj_strs = [
                    ob.get("statement", str(ob)) if isinstance(ob, dict) else str(ob)
                    for ob in objs
                ]
                lines.append(f"  Objections: {'; '.join(obj_strs)}")
            audience_blocks.append("\n".join(lines))
        audiences_str = "\n\n".join(audience_blocks)

        context_block = (
            f"## {spec.name}\n\n"
            f"**Positioning:** {spec.positioning or '(not set)'}\n"
            f"**Tagline:** {spec.tagline or '(not set)'}\n"
            f"**Differentiation:** {spec.differentiation or '(not set)'}\n"
            f"**Audience:** {spec.audience or '(not set)'}\n"
            f"**Brand Personality:** {spec.brand_personality or '(not set)'}\n\n"
            f"## Key Messages ({len(messages)} total, all sections)\n\n"
            f"{key_messages_str}\n\n"
            f"## Personas ({len(audiences)} total)\n\n"
            f"{audiences_str}"
        )

        # Safe single-item values for skill templates that reference {audience} / {qa_pairs}
        first_audience = audiences[0] if audiences else None
        first_obj_list: list[str] = []
        if first_audience:
            for ob in (first_audience.qa_pairs or []):
                first_obj_list.append(
                    ob.get("statement", str(ob)) if isinstance(ob, dict) else str(ob)
                )

        # Structured arrays for templating / design spec placeholder resolution
        benefits = [m.content for m in messages if str(m.assertion_type).split(".")[-1].lower() == "benefit"]
        all_qa_pairs = []
        for p in audiences:
            for ob in (p.qa_pairs or []):
                if isinstance(ob, dict):
                    all_qa_pairs.append(ob.get("statement", str(ob)) or "")
                else:
                    all_qa_pairs.append(str(ob))
        pillars_list = [{"name": pl.name, "description": pl.description} for pl in (getattr(spec, "pillars", []) or [])]
        audiences_list = [{"name": p.name, "description": p.description, "qa_pairs": p.qa_pairs} for p in audiences]
        structured_km = [{"assertion_type": str(m.assertion_type).split(".")[-1].lower(), "content": m.content} for m in messages]

        context = {
            "spec_name": spec.name,
            "positioning": spec.positioning or "",
            "tagline": spec.tagline or "",
            "differentiation": spec.differentiation or "",
            "audience": spec.audience or "",
            "assertions": key_messages_str,
            "audiences_detail": audiences_str,
            "context": context_block,
            "primary_message": messages[0].content if messages else "",
            "audience": first_audience.name if first_audience else "",
            "qa_pairs_str": "; ".join(first_obj_list) if first_obj_list else "",
            "benefits": benefits,
            "qa_pairs": all_qa_pairs,
            "pillars": pillars_list,
            "audiences": audiences_list,
            "structured_key_messages": structured_km,
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
