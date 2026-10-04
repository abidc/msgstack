"""Skill-based artifact generator using LLM + skills + grounding context."""

import json
import logging
import os
import re
from typing import Optional
from uuid import UUID

log = logging.getLogger(__name__)

# Per-entry tier directives injected into the grounding block (canon_domain §4.9).
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

from src.models import CanonDomain, CanonEntry, Persona
from src.store import Store
from src.pipeline.skills import SkillManager
from src.design.validators import DesignSpec, validate_and_fill_design_spec
from src.rendering.renderer import get_renderer, RenderOutput


class ArtifactRequest(BaseModel):
    skill_id: str
    canon_domain_id: str
    context: dict = {}


class GeneratedArtifact(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    skill_id: str
    canon_domain_id: str
    canon_domain_name: str
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


# Word-overlap scores in this band are too close to call by the crude heuristic
# alone (a true paraphrase and a verbatim quote with minor reordering can land
# on either side of a single fixed threshold) — refine via decide() instead of
# guessing. Outside this band the heuristic's call stands on its own.
_BORDERLINE_OVERLAP_BAND = (0.4, 0.8)


def find_tier1_violations(messages: list, output: str, refine_borderline: bool = True) -> list[dict]:
    """Detect Tier 1 entries that appear to have been used but not verbatim.

    An entry counts as "used" when most of its significant words appear in the
    output (fuzzy match); it passes when its whitespace-normalized text appears
    as an exact substring. Used-but-not-verbatim → violation.

    Overlap scores inside _BORDERLINE_OVERLAP_BAND are ambiguous for the fixed
    0.6 threshold alone; when `refine_borderline` is set (the default), those
    cases get a second opinion from decide() — a fixed-option "is this a
    violation: yes/no" call, cheap by design whether it runs on a self-hosted
    decision model or falls back to the existing LLM routing. Set to False in
    hot paths that can't tolerate the extra call (e.g. a tight generation loop)
    and accept the heuristic's threshold-only answer instead.
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
        is_violation = overlap >= 0.6
        lo, hi = _BORDERLINE_OVERLAP_BAND
        if refine_borderline and lo <= overlap <= hi:
            refined = _refine_borderline_violation(m.content, output)
            if refined is not None:
                is_violation = refined
        if is_violation:
            violations.append({
                "entry_id": str(getattr(m, "id", "")),
                "content": m.content,
                "word_overlap": round(overlap, 2),
                "warning": "Tier 1 entry appears to have been paraphrased — it must be reproduced verbatim.",
            })
    return violations


def _refine_borderline_violation(entry_content: str, output: str) -> Optional[bool]:
    """Second opinion for a borderline word-overlap score, via a decision model.

    Only attempted when a decision-model endpoint is actually configured — the
    whole point is a sub-500ms, cheap-by-construction call. Falling back to a
    full LLM call here instead would reintroduce the latency/cost the
    decision-model pattern exists to avoid, for marginal accuracy gain over an
    already-reasonable heuristic. None (keep the heuristic's answer) when no
    endpoint is configured or the call fails.
    """
    from src.config import settings
    if not settings.decision_model_url:
        return None
    try:
        from src.decision_model import decide
        result = decide(
            options=["violation", "not_a_violation"],
            prompt=(
                "A piece of content was supposed to be reproduced verbatim (word-for-word) "
                "but a heuristic found only partial word overlap, which is ambiguous. Given "
                "the locked source text and the generated output it should appear in, is this "
                "a genuine paraphrase (a violation) or a verbatim/near-verbatim reproduction "
                "with incidental differences, like surrounding punctuation or quoting (not a "
                "violation)?"
            ),
            context=f"LOCKED SOURCE TEXT: {entry_content}\n\nGENERATED OUTPUT: {output}",
        )
        return result.choice == "violation"
    except Exception:
        log.warning("Borderline Tier 1 refinement failed; keeping heuristic's threshold call", exc_info=True)
        return None


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

    def generate(self, skill_id: str, canon_domain_id: str, custom_context: dict = None) -> GeneratedArtifact:
        skill = self.skills.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")

        canon_domain = self.store.get_canon_domain(UUID(canon_domain_id))
        if not canon_domain:
            raise ValueError(f"CanonDomain {canon_domain_id} not found")

        messages = self.store.get_key_messages(canon_domain.id, include_unapproved=True)
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

        personas = self.store.get_personas(canon_domain.id)

        # Check if this is a visual artifact type
        artifact_type = skill.get("prefab_template") or skill_id
        is_visual = skill.get("renderer") == "fabric"

        context = self._build_context(canon_domain, messages, personas, custom_context or {})

        # Audience Profile: formalizes what used to be an ad-hoc per-entry
        # `variants` dict into enforced tone/style constraints. An explicit
        # tone_professionalism/tone_warmth in custom_context still wins over
        # the profile's defaults — the profile only fills gaps, never overrides
        # a caller who passed sliders directly.
        audience_profile = None
        if custom_context and custom_context.get("audience_profile_id"):
            audience_profile = self.store.get_audience_profile(UUID(custom_context["audience_profile_id"]))

        # Tonal sliders mapping:
        tone_register = ""
        if custom_context or audience_profile:
            ctx = custom_context or {}
            default_prof = audience_profile.tone_professionalism if audience_profile else 0.5
            default_warm = audience_profile.tone_warmth if audience_profile else 0.5
            professionalism = ctx.get("tone_professionalism", default_prof)
            warmth = ctx.get("tone_warmth", default_warm)
            # Map float sliders to specific prompt instructions
            tone_register = (
                f"\nTONE & REGISTER BOUNDS:\n"
                f"- Professionalism level: {professionalism} (1.0 = highly formal, 0.0 = highly casual)\n"
                f"- Warmth level: {warmth} (1.0 = highly friendly, 0.0 = highly objective and technical)\n"
                f"Adjust output register to match these bounds while respecting brand personality."
            )
            if audience_profile:
                tone_register += f"\n- Reading level: {audience_profile.reading_level}."
                if audience_profile.required_cta:
                    tone_register += f"\n- Must end with a call to action equivalent to: \"{audience_profile.required_cta}\""

        # For visual artifacts, pre-fill template zones before LLM call
        visual_context = None
        template = None
        if is_visual:
            template = self._get_template(artifact_type)
            if template:
                visual_context = self._build_visual_context(
                    canon_domain_id, template, artifact_type, canon_domain, messages, personas
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
        
        try:
            from src.pipeline.vocabulary import apply_controlled_vocabulary
            raw = apply_controlled_vocabulary(raw, canon_domain.id, self.store)
            if audience_profile and audience_profile.banned_phrases:
                for phrase in audience_profile.banned_phrases:
                    if phrase and phrase.lower() in raw.lower():
                        raw = re.sub(re.escape(phrase), "", raw, flags=re.IGNORECASE)
                        log.warning("Audience profile %s banned phrase %r found and stripped from output",
                                    audience_profile.name, phrase)
            if audience_profile and audience_profile.required_cta and audience_profile.required_cta.lower() not in raw.lower():
                log.warning("Audience profile %s required a CTA ('%s') not found in generated output — not enforced, flagged for review",
                             audience_profile.name, audience_profile.required_cta)
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
        
        # Get canon_domain_name for context
        render_context = {"canon_domain_name": canon_domain.name}
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
                skill_id, canon_domain_id, len(tier_violations),
            )

        return GeneratedArtifact(
            skill_id=skill_id,
            canon_domain_id=canon_domain_id,
            canon_domain_name=canon_domain.name,
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
        canon_domain_id: str,
        template: dict,
        artifact_type: str,
        canon_domain: CanonDomain,
        messages: list[CanonEntry],
        personas: list[Persona],
    ) -> dict:
        """
        Pre-assign messaging canon_domain content to template zones BEFORE the LLM call.
        Maps:
        - tagline → hero.text_content
        - positioning → hero.body
        - differentiation → pillar_grid
        - top 6 key messages by priority → message_list
        - personas → audience_strip (max 3, primary first)
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
                if canon_domain.tagline:
                    content["text"] = canon_domain.tagline[:max_chars]
                # Also map positioning → hero.body if there's a body sub-zone
                if zone_id.endswith("_body") and canon_domain.positioning:
                    content["text"] = canon_domain.positioning[:max_chars]

            elif zone_type == "positioning":
                if canon_domain.positioning:
                    content["text"] = canon_domain.positioning[:max_chars]

            elif zone_type == "pillar_grid" or zone_type == "differentiation":
                # Map differentiation → pillar_grid
                if canon_domain.differentiation:
                    items = [item.strip() for item in canon_domain.differentiation.split(".") if item.strip()][:capacity]
                    content["items"] = items

            elif zone_type == "message_list":
                # Top 6 key messages by priority
                all_msgs = []
                for section_msgs in by_section.values():
                    all_msgs.extend(section_msgs)
                all_msgs.sort(key=lambda x: x.priority or 3)
                content["items"] = [m.content[:max_chars] for m in all_msgs[:capacity * 2][:6]]

            elif zone_type == "audience_strip":
                # Persona truncation: max 3 personas, primary first, then by completeness
                sorted_audiences = sorted(
                    personas,
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
                # Pull objections + responses from graph for verbatim accuracy
                qa_pair_items = []
                for p in personas:
                    objs = p.objections or []
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
        """Generate fallback design canon_domain with template defaults."""
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
        canon_domain: CanonDomain,
        messages: list[CanonEntry],
        personas: list[Persona],
        custom: dict,
    ) -> dict:
        # Tier affects ordering and annotation ONLY — never inclusion. Untier'd
        # (legacy NULL-tier) entries are always included, sorted after tiered ones.
        # Unset tier blocks *promotion* (update_entry_status), not generation.
        tier_order = {"tier_1_locked": 0, "tier_2_structured": 1, "tier_3_grounded": 2}
        # Group ALL messages by section type, sorted by tier then priority within each group
        by_section: dict[str, list[CanonEntry]] = {}
        for m in messages:
            key = str(m.section_type)
            by_section.setdefault(key, []).append(m)

        section_blocks = []
        for section_type in sorted(by_section):
            msgs = sorted(by_section[section_type], key=lambda x: (tier_order.get(getattr(x, "content_tier", None) or "", 99), x.priority or 3))
            section_blocks.append(f"### {section_type.upper().replace('_', ' ')} ({len(msgs)})")
            for m in msgs:
                directive = TIER_DIRECTIVES.get(getattr(m, "content_tier", None) or "", "")
                section_blocks.append(f"  - {directive}{m.content}")
        key_messages_str = "\n".join(section_blocks)

        # Build full persona blocks — all personas, all attributes
        audience_blocks = []
        for p in personas:
            lines = [f"**{p.name}**"]
            if p.description:
                lines.append(f"  Description: {p.description}")
            pain = p.objections or []
            if pain:
                lines.append(f"  Pain Points: {'; '.join(str(x) for x in pain)}")
            triggers = []
            if triggers:
                lines.append(f"  Buying Triggers: {'; '.join(str(x) for x in triggers)}")
            objs = p.objections or []
            if objs:
                obj_strs = [
                    ob.get("statement", str(ob)) if isinstance(ob, dict) else str(ob)
                    for ob in objs
                ]
                lines.append(f"  Objections: {'; '.join(obj_strs)}")
            audience_blocks.append("\n".join(lines))
        audiences_str = "\n\n".join(audience_blocks)

        context_block = (
            f"## {canon_domain.name}\n\n"
            f"**Positioning:** {canon_domain.positioning or '(not set)'}\n"
            f"**Tagline:** {canon_domain.tagline or '(not set)'}\n"
            f"**Differentiation:** {canon_domain.differentiation or '(not set)'}\n"
            f"**Audience:** {canon_domain.audience or '(not set)'}\n"
            f"**Brand Personality:** {canon_domain.brand_personality or '(not set)'}\n\n"
            f"## Key Messages ({len(messages)} total, all sections)\n\n"
            f"{key_messages_str}\n\n"
            f"## Personas ({len(personas)} total)\n\n"
            f"{audiences_str}"
        )

        # Safe single-item values for skill templates that reference {persona} / {objections}
        first_audience = personas[0] if personas else None
        first_obj_list: list[str] = []
        if first_audience:
            for ob in (first_audience.objections or []):
                first_obj_list.append(
                    ob.get("statement", str(ob)) if isinstance(ob, dict) else str(ob)
                )

        # Structured arrays for templating / design canon_domain placeholder resolution
        benefits = [m.content for m in messages if str(m.section_type).split(".")[-1].lower() == "benefit"]
        all_qa_pairs = []
        for p in personas:
            for ob in (p.objections or []):
                if isinstance(ob, dict):
                    all_qa_pairs.append(ob.get("statement", str(ob)) or "")
                else:
                    all_qa_pairs.append(str(ob))
        pillars_list = [{"name": pl.name, "description": pl.description} for pl in (getattr(canon_domain, "pillars", []) or [])]
        audiences_list = [{"name": p.name, "description": p.description, "objections": p.objections} for p in personas]
        structured_km = [{"section_type": str(m.section_type).split(".")[-1].lower(), "content": m.content} for m in messages]

        context = {
            "canon_domain_name": canon_domain.name,
            "positioning": canon_domain.positioning or "",
            "tagline": canon_domain.tagline or "",
            "differentiation": canon_domain.differentiation or "",
            "audience": canon_domain.audience or "",
            "key_messages": key_messages_str,
            "personas_detail": audiences_str,
            "context": context_block,
            "primary_message": messages[0].content if messages else "",
            "persona": first_audience.name if first_audience else "",
            "qa_pairs_str": "; ".join(first_obj_list) if first_obj_list else "",
            "benefits": benefits,
            "objections": all_qa_pairs,
            "pillars": pillars_list,
            "personas": audiences_list,
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
