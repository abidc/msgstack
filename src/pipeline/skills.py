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
        "description": "A structured overview of a messaging house with positioning, key messages, and personas.",
        "channels": ["all"],
        "sections": [
            {"key": "positioning", "label": "Positioning Statement", "required": True},
            {"key": "tagline", "label": "Tagline", "required": False},
            {"key": "differentiation", "label": "Differentiation", "required": True},
            {"key": "key_messages", "label": "Key Messages", "required": True},
            {"key": "personas", "label": "Target Personas", "required": True},
        ],
        "prompt_template": """Generate a one-pager for {house_name} grounded in this messaging framework:

{context}

Structure the one-pager with:
1. Positioning statement (2-3 sentences)
2. Tagline (7 words or fewer)
3. Key differentiation points (3 bullets)
4. Top 3 key messages by section type
5. Primary and secondary personas with pain points

Output as structured markdown.""",
        "prefab_template": "one_pager",
    },
    "linkedin_post": {
        "id": "linkedin_post",
        "name": "LinkedIn Post",
        "description": "A LinkedIn post grounded in messaging for a specific section type.",
        "channels": ["linkedin"],
        "sections": [
            {"key": "hook", "label": "Hook (first line)", "required": True},
            {"key": "body", "label": "Body", "required": True},
            {"key": "cta", "label": "Call to Action", "required": False},
            {"key": "hashtags", "label": "Hashtags", "required": False},
        ],
        "prompt_template": """Write a LinkedIn post grounded in {house_name} messaging.

Core message: {primary_message}
Persona: {persona}

Rules:
- Hook in the first line must stop the scroll (question, bold claim, or contrarian take)
- Body expands the hook with concrete value — no fluffy intro
- 150-300 words total
- Include a natural CTA that doesn't feel salesy
- 2-3 relevant hashtags at the end
- Do NOT use emojis
- Write in first person plural ("we", "our") not brand voice""",
        "prefab_template": "social_post",
    },
    "email_template": {
        "id": "email_template",
        "name": "Email Template",
        "description": "A funnel-stage email (awareness, consideration, decision).",
        "channels": ["email"],
        "stages": ["awareness", "consideration", "decision"],
        "sections": [
            {"key": "subject", "label": "Subject Line", "required": True},
            {"key": "preview", "label": "Preview Text", "required": False},
            {"key": "hook", "label": "Hook / Opening", "required": True},
            {"key": "body", "label": "Body Copy", "required": True},
            {"key": "cta", "label": "Call to Action", "required": True},
        ],
        "prompt_template": """Write an email at the {stage} stage for {house_name}.

Grounded in this positioning: {positioning}

Key message: {primary_message}
Target persona: {persona}

Rules:
- Subject line: max 60 chars, curiosity-driven, no clickbait
- Preview text: max 90 chars, extends the subject
- Hook: 1-2 sentences, lead with the insight not the product
- Body: {stage} stage tone — awareness = educate, consideration = compare, decision = convert
- CTA: singular, specific, low friction
- Output subject, preview, hook, body, and CTA as separate fields""",
        "prefab_template": "email_template",
    },
    "battlecard": {
        "id": "battlecard",
        "name": "Competitive Battlecard",
        "description": "A structured comparison card against a named competitor.",
        "channels": ["all"],
        "sections": [
            {"key": "competitor", "label": "Competitor Name", "required": True},
            {"key": "our_strengths", "label": "Our Strengths vs Competitor", "required": True},
            {"key": "their_weaknesses", "label": "Competitor Weaknesses", "required": True},
            {"key": "counter_messaging", "label": "Counter Messaging", "required": True},
            {"key": "proof_points", "label": "Proof Points", "required": True},
        ],
        "prompt_template": """Write a battlecard for {house_name} against {competitor}.

Our positioning: {positioning}
Our key advantages: {key_messages}

Structure:
1. Competitor overview (1 paragraph — what they're known for)
2. Our strengths vs theirs (3-4 bullets — specific, evidence-backed)
3. Where they fall short (2-3 bullets — cite specific weaknesses)
4. Counter messaging (2-3 response templates for common objections)
5. Proof points (stats, customer quotes, analyst data)

Tone: confident, factual, never disparaging""",
        "prefab_template": "battlecard",
    },
    "press_release": {
        "id": "press_release",
        "name": "Press Release",
        "description": "A formal press release announcement.",
        "channels": ["all"],
        "sections": [
            {"key": "headline", "label": "Headline", "required": True},
            {"key": "subhead", "label": "Subheadline", "required": False},
            {"key": "dateline", "label": "Dateline", "required": True},
            {"key": "lead", "label": "Lead Paragraph", "required": True},
            {"key": "body", "label": "Body", "required": True},
            {"key": "quote_1", "label": "Executive Quote", "required": True},
            {"key": "quote_2", "label": "Customer Quote", "required": False},
            {"key": "boilerplate", "label": "Boilerplate", "required": True},
            {"key": "media_contact", "label": "Media Contact", "required": True},
        ],
        "prompt_template": """Write a press release for {house_name} announcing {announcement}.

Grounded in: {positioning}

Rules:
- Follow AP style
- Lead paragraph answers: who, what, when, where, why in 35 words or fewer
- Headline is the story, not the company name
- Executive quote: specific outcome, no marketing superlatives
- Boilerplate: 75 words about the company
- Include media contact with name, email, phone""",
        "prefab_template": "press_release",
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
        "prompt_template": """Write a blog post for {house_name} on the topic of {topic}.

Grounded in: {positioning}
Key messages to weave in: {key_messages}
Persona: {persona}

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
        "prompt_template": """Write an FAQ document for {house_name} addressing {audience} questions.

Grounded in: {positioning}
Common objections to address: {objections}

Rules:
- Organize by theme (Product, Pricing, Security, Integration, Support)
- Each Q is a real question a prospect would ask — not a softballs
- Each A is direct, confident, and grounded in the positioning
- 8-12 Q&A pairs minimum
- Include an 'Other questions?' section at the end""",
        "prefab_template": "faq_document",
    },
}


class SkillManager:
    def __init__(self, skills_dir: str | Path = "skills"):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        for skill_id, skill in DEFAULT_SKILLS.items():
            path = self.skills_dir / f"{skill_id}.json"
            if not path.exists():
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