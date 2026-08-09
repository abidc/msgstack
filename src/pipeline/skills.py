"""Artifact skill file manager — JSON skill files per artifact type."""

import json
import os
from pathlib import Path
from typing import Optional
from uuid import uuid4


DEFAULT_SKILLS = {
    "one_pager": {
        "id": "one_pager",
        "name": "One-Pager",
        "description": "A structured overview of a messaging spec with positioning, key messages, and audiences.",
        "channels": ["all"],
        "sections": [
            {"key": "positioning", "label": "Positioning Statement", "required": True},
            {"key": "tagline", "label": "Tagline", "required": False},
            {"key": "differentiation", "label": "Differentiation", "required": True},
            {"key": "assertions", "label": "Key Messages", "required": True},
            {"key": "audiences", "label": "Target Personas", "required": True},
        ],
        "prompt_template": """Generate a one-pager for {spec_name} grounded in this messaging framework:

{context}

Structure the one-pager with:
1. Positioning statement (2-3 sentences)
2. Tagline (7 words or fewer)
3. Key differentiation points (3 bullets)
4. Top 3 key messages by section type
5. Primary and secondary audiences with pain points

Output as structured markdown.""",
        "prefab_template": "one_pager",
    },
    "blog_post": {
        "id": "blog_post",
        "name": "Blog Post",
        "description": "A long-form blog post on a topic grounded in the messaging.",
        "channels": ["blog"],
        "sections": [
            {"key": "title", "label": "Title", "required": True},
            {"key": "meta_description", "label": "Meta Description", "required": True},
            {"key": "intro", "label": "Introduction", "required": True},
            {"key": "sections", "label": "Body Sections", "required": True},
            {"key": "conclusion", "label": "Conclusion", "required": True},
            {"key": "cta", "label": "Call to Action", "required": True},
        ],
        "prompt_template": """Write a blog post for {spec_name} on the topic of {topic}.

Grounded in: {positioning}
Key messages to weave in: {assertions}
Audience: {audience}

Rules:
- Title: SEO-optimized, benefit-led, 60 chars or fewer
- Meta: 155 chars or fewer
- Intro: hook + roadmap (what the reader will learn)
- Body: {target_length} words, H2/H3 structure, 3-5 sections
- Weave key messages naturally — don't just list them
- Include a relevant data point or stat where possible
- Conclusion: summarize + CTA
- Tone: {tone}""",
        "prefab_template": "blog_post",
    },
    "faq_document": {
        "id": "faq_document",
        "name": "FAQ Document",
        "description": "A Q&A document addressing common customer and prospect questions.",
        "channels": ["all"],
        "sections": [
            {"key": "category", "label": "Question Category", "required": True},
            {"key": "q", "label": "Question", "required": True},
            {"key": "a", "label": "Answer", "required": True},
        ],
        "prompt_template": """Write an FAQ document for {spec_name} addressing {audience} questions.

Grounded in: {positioning}
Common qa_pairs to address: {qa_pairs}

Rules:
- Organize by theme (Product, Pricing, Security, Integration, Support)
- Each Q is a real question a prospect would ask — not a softballs
- Each A is direct, confident, and grounded in the positioning
- 8-12 Q&A pairs minimum
- Include an 'Other questions?' section at the end""",
        "prefab_template": "faq_document",
    },
    "executive_summary": {
        "id": "executive_summary",
        "name": "Executive Summary",
        "description": "C-level briefing format — business case, strategic fit, and decision criteria.",
        "channels": ["all"],
        "sections": [
            {"key": "situation", "label": "Situation", "required": True},
            {"key": "complication", "label": "Complication / Risk", "required": True},
            {"key": "resolution", "label": "Resolution / Recommendation", "required": True},
            {"key": "business_case", "label": "Business Case", "required": True},
            {"key": "next_steps", "label": "Next Steps", "required": True},
        ],
        "prompt_template": """Write an executive summary for {spec_name} targeted at C-level decision makers.

Grounded in: {positioning}
Key proof points: {assertions}
Target executive audience: {audience}

Use the SCR (Situation-Complication-Resolution) framework:
1. Situation (1 paragraph): The current state — what is the executive already dealing with?
2. Complication (1 paragraph): What's the problem or risk if nothing changes?
3. Resolution (1 paragraph): How {spec_name} addresses it specifically
4. Business case (bullet points): 3 quantified outcomes or ROI data points
5. Next steps: 2-3 low-friction action items with owners and timeline

Rules:
- No jargon, no product feature lists
- Lead with business outcomes, not capabilities
- Under 400 words total
- Each section starts with a bold topic sentence""",
        "prefab_template": "executive_summary",
    },
    "one_pager_visual": {
        "id": "one_pager_visual",
        "name": "Visual One-Pager (Canvas)",
        "description": "A visual, graphical one-pager layout generated as a Fabric.js design specification.",
        "channels": ["all"],
        "sections": [
            {"key": "design_spec", "label": "Design JSON Specification", "required": True},
        ],
        "prompt_template": """Generate a structured design specification for a visual One-Pager for {spec_name}.

TEMPLATE ZONE STRUCTURE (injected below — DO NOT modify zone IDs or types):
{visual_context}

GROUNDING REMINDER:
- Use ONLY content from the messaging spec below.
- Do NOT invent headlines, stats, or claims.
- Copy pre-filled zone content EXACTLY (edit only for tone/polish).

SPEC DATA:
- Tagline: {tagline} (keep under 10 words)
- Positioning: {positioning}
- Differentiation: {differentiation}
- Top messages: {assertions}

OUTPUT FORMAT (return ONLY this JSON in `design_spec`):
{{
  "zones": [
    {{ "id": "hero", "type": "hero", "text_content": "Pre-filled tagline here" }},
    {{ "id": "positioning_block", "type": "positioning_block", "text_content": "Pre-filled positioning..." }},
    {{ "id": "pillar_grid", "type": "pillar_grid", "list_items": ["Point 1", "Point 2", "Point 3"] }}
  ]
}}

RULES:
- hero.text_content MUST be the tagline (under 10 words)
- positioning_block.text_content MUST be the positioning statement
- pillar_grid shows exactly 3 differentiation points
- message_list shows top 6 key messages by priority
- audience_strip shows max 3 audiences (primary first)
- proof_block shows top 3 proof points""",
        "prefab_template": "one_pager_visual",
        "renderer": "fabric"
    },
    "datasheet": {
        "id": "datasheet",
        "name": "Data Sheet",
        "description": "A technical data sheet with specs, features, and benefits.",
        "channels": ["all"],
        "sections": [
            {"key": "design_spec", "label": "Design JSON Specification", "required": True},
        ],
        "prompt_template": """Generate a structured design specification for a Data Sheet for {spec_name}.

TEMPLATE ZONE STRUCTURE (injected below — DO NOT modify zone IDs or types):
{visual_context}

GROUNDING REMINDER:
- Use ONLY content from the messaging spec below.
- Do NOT invent specs, features, or benefits.
- Copy pre-filled zone content EXACTLY (edit only for tone/polish).

SPEC DATA:
- Tagline: {tagline}
- Positioning: {positioning}
- Key Benefits: {assertions}

OUTPUT FORMAT (return ONLY this JSON in `design_spec`):
{{
  "zones": [
    {{ "id": "header", "type": "header", "text_content": "Product Name | Tagline" }},
    {{ "id": "hero", "type": "hero", "text_content": "Positioning statement goes here..." }},
    {{ "id": "benefits_grid", "type": "pillar_grid", "list_items": ["Benefit 1", "Benefit 2", "Benefit 3"] }},
    {{ "id": "proof", "type": "proof_block", "text_content": "Proof point or key stat..." }},
    {{ "id": "cta_footer", "type": "cta_footer", "text_content": "Contact / CTA details..." }}
  ]
}}

RULES:
- header.text_content MUST include tagline
- hero.text_content MUST contain the main positioning statement
- benefits_grid shows top benefits (max 6)
- proof.text_content shows a proof point with stats
- cta_footer.text_content contains the call to action""",
        "prefab_template": "datasheet",
        "renderer": "fabric"
    },
    "executive_summary_visual": {
        "id": "executive_summary_visual",
        "name": "Executive Summary (Visual)",
        "description": "A designed C-level briefing document.",
        "channels": ["all"],
        "sections": [
            {"key": "design_spec", "label": "Design JSON Specification", "required": True},
        ],
        "prompt_template": """Generate a structured design specification for a Visual Executive Summary for {spec_name}.

TEMPLATE ZONE STRUCTURE (injected below — DO NOT modify zone IDs or types):
{visual_context}

GROUNDING REMINDER:
- Use SCR (Situation-Complication-Resolution) framework.
- Lead with business outcomes.
- Output MUST align with template fields.

OUTPUT FORMAT (return ONLY this JSON in `design_spec`):
{{
  "zones": [
    {{ "id": "header", "type": "header", "text_content": "{spec_name} | Executive Summary" }},
    {{ "id": "positioning", "type": "positioning_block", "text_content": "Full positioning paragraph" }},
    {{ "id": "pillars", "type": "pillar_grid", "list_items": ["Pillar 1", "Pillar 2", "Pillar 3"] }},
    {{ "id": "audience_strip", "type": "audience_strip", "list_items": ["Audience 1", "Audience 2"] }},
    {{ "id": "proof", "type": "proof_block", "text_content": "Top ROI stat or outcome" }},
    {{ "id": "cta_footer", "type": "cta_footer", "text_content": "Next steps / Website" }}
  ]
}}

RULES:
- No jargon, no product feature lists
- pillars MUST contain exactly 3 strategic pillars
- proof MUST be a quantified outcome or ROI point""",
        "prefab_template": "executive_summary",
        "renderer": "fabric"
    },
}


SKILL_CONTEXT_INPUTS: dict[str, list[dict]] = {
    "battlecard": [
        {"key": "competitor", "label": "Competitor Name", "placeholder": "e.g. Salesforce", "required": True},
    ],
    "battlecard_visual": [
        {"key": "competitor", "label": "Competitor Name", "placeholder": "e.g. Salesforce", "required": True},
    ],
    "email_template": [
        {"key": "stage", "label": "Funnel Stage", "options": ["awareness", "consideration", "decision"], "required": False, "default": "awareness"},
    ],
    "blog_post": [
        {"key": "topic", "label": "Blog Topic", "placeholder": "e.g. AI in enterprise software", "required": True},
        {"key": "target_length", "label": "Word Count", "options": ["500", "800", "1200", "1500"], "required": False, "default": "800"},
        {"key": "tone", "label": "Tone", "options": ["professional", "conversational", "technical", "thought-leadership"], "required": False, "default": "professional"},
    ],
    "press_release": [
        {"key": "announcement", "label": "Announcement Summary", "placeholder": "e.g. Series B funding round", "required": True},
    ],
    "event_brief": [
        {"key": "event_name", "label": "Event Name", "placeholder": "e.g. Dreamforce 2025", "required": True},
    ],
    "datasheet": [
        {"key": "specs", "label": "Technical Specs", "placeholder": "e.g. 99.9% uptime", "required": False},
    ],
}


class SkillManager:
    def __init__(self, skills_dir: str | Path = "skills"):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        # Always write built-in defaults so prompt template improvements land automatically.
        # User-created custom skills (IDs not in DEFAULT_SKILLS) are never touched.
        for skill_id, skill in DEFAULT_SKILLS.items():
            self._save_skill(skill_id, skill)

    def _save_skill(self, skill_id: str, data: dict) -> None:
        path = self.skills_dir / f"{skill_id}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def list_skills(self) -> list[dict]:
        skills = []
        for path in sorted(self.skills_dir.glob("*.json")):
            with open(path) as f:
                skills.append(json.load(f))
        return skills

    def get_skill(self, skill_id: str) -> Optional[dict]:
        path = self.skills_dir / f"{skill_id}.json"
        if not path.exists():
            return DEFAULT_SKILLS.get(skill_id)
        with open(path) as f:
            return json.load(f)

    def update_skill(self, skill_id: str, data: dict) -> dict:
        data["id"] = skill_id
        self._save_skill(skill_id, data)
        return data

    def delete_skill(self, skill_id: str) -> bool:
        path = self.skills_dir / f"{skill_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def fill_prompt(
        self, skill_id: str, context: dict, custom_template: Optional[str] = None
    ) -> str:
        """Fill a skill's prompt template with a given context."""
        skill = self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")

        template = custom_template or skill["prompt_template"]
        try:
            return template.format(**context)
        except KeyError as e:
            raise ValueError(f"Missing context key for skill {skill_id}: {e}")

    def get_sections(self, skill_id: str) -> list[dict]:
        skill = self.get_skill(skill_id)
        if not skill:
            return []
        return skill.get("sections", [])

    def get_context_inputs(self, skill_id: str) -> list[dict]:
        return SKILL_CONTEXT_INPUTS.get(skill_id, [])