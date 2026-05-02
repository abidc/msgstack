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
    "talk_track": {
        "id": "talk_track",
        "name": "Sales Talk Track",
        "description": "Stage-by-stage sales call script with discovery questions and value statements.",
        "channels": ["all"],
        "sections": [
            {"key": "opener", "label": "Call Opener", "required": True},
            {"key": "discovery", "label": "Discovery Questions", "required": True},
            {"key": "value_prop", "label": "Value Proposition", "required": True},
            {"key": "demo_focus", "label": "Demo Focus Points", "required": True},
            {"key": "objection_handling", "label": "Common Objections + Responses", "required": True},
            {"key": "close", "label": "Close / Next Steps", "required": True},
        ],
        "prompt_template": """Write a sales talk track for {house_name}.

Grounded in: {positioning}
Key differentiators: {key_messages}
Target persona: {persona}

Structure:
1. Call opener (30 seconds, hook the prospect immediately)
2. 5-7 discovery questions that uncover pain points specific to this persona
3. Value proposition statement (2-3 sentences tied to their likely pain points)
4. Demo focus points (top 3 capabilities to show — ordered by persona priority)
5. 4-5 common objections with specific, confident counter-responses
6. Close / next steps (2 options for low-friction progression)

Tone: consultative, confident, not pushy. Ask questions before pitching.""",
        "prefab_template": "talk_track",
    },
    "objection_handler": {
        "id": "objection_handler",
        "name": "Objection Handler",
        "description": "Full objection/rebuttal reference card for common sales and marketing objections.",
        "channels": ["all"],
        "sections": [
            {"key": "objection", "label": "Objection", "required": True},
            {"key": "root_cause", "label": "Root Cause", "required": True},
            {"key": "response", "label": "Response", "required": True},
            {"key": "proof", "label": "Supporting Proof Point", "required": False},
        ],
        "prompt_template": """Write a comprehensive objection handler reference card for {house_name}.

Grounded in: {positioning}
Known objections from personas: {objections}

For each objection:
1. State the objection verbatim as a prospect would say it
2. Identify the root cause (fear, misunderstanding, prior bad experience)
3. Write a 2-3 sentence response: acknowledge → reframe → redirect
4. Add a supporting proof point or stat where possible

Cover at least 8 objections across these categories:
- Price / ROI objections
- Complexity / implementation concerns
- "We already have a solution" objections
- Timing / priority objections
- Trust / credibility objections

Tone: empathetic, factual, never defensive.""",
        "prefab_template": "objection_handler",
    },
    "event_brief": {
        "id": "event_brief",
        "name": "Event Brief",
        "description": "Conference or event messaging brief with talking points and booth/session strategy.",
        "channels": ["all"],
        "sections": [
            {"key": "event_theme", "label": "Event Theme & Audience", "required": True},
            {"key": "our_angle", "label": "Our Angle / Key Message", "required": True},
            {"key": "talking_points", "label": "Top 3 Talking Points", "required": True},
            {"key": "demo_story", "label": "Demo Story", "required": True},
            {"key": "booth_hooks", "label": "Booth / Session Hooks", "required": False},
            {"key": "follow_up", "label": "Post-Event Follow-up Messaging", "required": True},
        ],
        "prompt_template": """Write an event messaging brief for {house_name} at {event_name}.

Grounded in: {positioning}
Key audience at this event: {audience}
Primary message to land: {primary_message}

Structure:
1. Event theme and attendee profile (who will be in the room, what they care about)
2. Our angle — the single idea we want every attendee to walk away with
3. Top 3 talking points tailored to this specific audience
4. Demo story (3-minute narrative arc: before → after → proof)
5. Booth/session hook (what gets someone to stop, come in, stay)
6. Post-event follow-up email subject lines and first-line hooks (3 options)

Tone: energetic but credible. Avoid generic conference buzzwords.""",
        "prefab_template": "event_brief",
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
        "prompt_template": """Write an executive summary for {house_name} targeted at C-level decision makers.

Grounded in: {positioning}
Key proof points: {key_messages}
Target executive persona: {persona}

Use the SCR (Situation-Complication-Resolution) framework:
1. Situation (1 paragraph): The current state — what is the executive already dealing with?
2. Complication (1 paragraph): What's the problem or risk if nothing changes?
3. Resolution (1 paragraph): How {house_name} addresses it specifically
4. Business case (bullet points): 3 quantified outcomes or ROI data points
5. Next steps: 2-3 low-friction action items with owners and timeline

Rules:
- No jargon, no product feature lists
- Lead with business outcomes, not capabilities
- Under 400 words total
- Each section starts with a bold topic sentence""",
        "prefab_template": "executive_summary",
    },
    "partner_brief": {
        "id": "partner_brief",
        "name": "Partner Brief",
        "description": "Channel partner messaging enablement sheet with co-sell angles and joint value proposition.",
        "channels": ["all"],
        "sections": [
            {"key": "joint_value_prop", "label": "Joint Value Proposition", "required": True},
            {"key": "partner_benefit", "label": "Why Partners Win with Us", "required": True},
            {"key": "target_customer", "label": "Ideal Joint Customer", "required": True},
            {"key": "co_sell_motion", "label": "Co-Sell Motion", "required": True},
            {"key": "field_messaging", "label": "Field-Ready Messaging", "required": True},
            {"key": "resources", "label": "Available Resources", "required": False},
        ],
        "prompt_template": """Write a channel partner messaging brief for {house_name}.

Our positioning: {positioning}
Our key differentiators: {key_messages}

Structure:
1. Joint value proposition (2-3 sentences: what we do together that neither does alone)
2. Why partners win with us (3 bullets: margin, stickiness, competitive advantage)
3. Ideal joint customer profile (firmographics + tech environment + pain points)
4. Co-sell motion (step-by-step: when to bring us in, how to position together)
5. Field-ready messaging (3 one-liners partners can use in customer conversations)
6. Available resources (sales tools, demo access, co-marketing options)

Tone: partner-first. Focus on what the partner gains, not what we gain.""",
        "prefab_template": "partner_brief",
    },
    "one_pager_visual": {
        "id": "one_pager_visual",
        "name": "Visual One-Pager (Canvas)",
        "description": "A visual, graphical one-pager layout generated as a Fabric.js design specification.",
        "channels": ["all"],
        "sections": [
            {"key": "design_spec", "label": "Design JSON Specification", "required": True},
        ],
        "prompt_template": """Generate a structured design specification for a visual One-Pager for {house_name}.

TEMPLATE ZONE STRUCTURE (injected below — DO NOT modify zone IDs or types):
{visual_context}

GROUNDING REMINDER:
- Use ONLY content from the messaging house below.
- Do NOT invent headlines, stats, or claims.
- Copy pre-filled zone content EXACTLY (edit only for tone/polish).

HOUSE DATA:
- Tagline: {tagline} (keep under 10 words)
- Positioning: {positioning}
- Differentiation: {differentiation}
- Top messages: {key_messages}

OUTPUT FORMAT (return ONLY this JSON in `design_spec`):
{{
  "zones": [
    {{ "id": "hero", "type": "hero", "content": {{ "text": "Pre-filled tagline here" }} }},
    {{ "id": "positioning_block", "type": "positioning", "content": {{ "text": "Pre-filled positioning..." }} }},
    {{ "id": "pillar_grid", "type": "pillar_grid", "content": {{ "items": ["Point 1", "Point 2", "Point 3"] }} }}
  ]
}}

RULES:
- hero.text_content MUST be the tagline (under 10 words)
- positioning.text MUST be the positioning statement
- pillar_grid shows exactly 3 differentiation points
- message_list shows top 6 key messages by priority
- persona_strip shows max 3 personas (primary first)
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
        "prompt_template": """Generate a structured design specification for a Data Sheet for {house_name}.

TEMPLATE ZONE STRUCTURE (injected below — DO NOT modify zone IDs or types):
{visual_context}

GROUNDING REMINDER:
- Use ONLY content from the messaging house below.
- Do NOT invent specs, features, or benefits.
- Copy pre-filled zone content EXACTLY (edit only for tone/polish).

HOUSE DATA:
- Tagline: {tagline}
- Positioning: {positioning}
- Key Benefits: {key_messages}

OUTPUT FORMAT (return ONLY this JSON in `design_spec`):
{{
  "zones": [
    {{ "id": "header", "type": "hero", "content": {{ "text": "Product Name | Tagline" }} }},
    {{ "id": "features", "type": "feature_grid", "content": {{ "items": ["Feature 1", "Feature 2"] }} }},
    {{ "id": "specs", "type": "spec_list", "content": {{ "items": ["Spec 1", "Spec 2"] }} }}
  ]
}}

RULES:
- header.text MUST include tagline
- feature_grid shows top benefits (max 6)
- spec_list shows technical specs from key messages
- proof_block shows 3 proof points with stats""",
        "prefab_template": "datasheet",
        "renderer": "fabric"
    },
    "battlecard_visual": {
        "id": "battlecard_visual",
        "name": "Visual Battlecard (Canvas)",
        "description": "A visual competitive battlecard with verbatim objections and responses.",
        "channels": ["all"],
        "sections": [
            {"key": "design_spec", "label": "Design JSON Specification", "required": True},
            {"key": "competitor", "label": "Competitor Name", "required": True},
        ],
        "prompt_template": """Generate a structured design specification for a Visual Battlecard for {house_name} against {competitor}.

TEMPLATE ZONE STRUCTURE (injected below — DO NOT modify zone IDs or types):
{visual_context}

GROUNDING REMINDER:
- Use ONLY objections/responses from the messaging house.
- Pull objections and responses from graph for VERBATIM accuracy.
- Copy pre-filled zone content EXACTLY (edit only for tone/polish).

COMPETITOR: {competitor}
OUR POSITIONING: {positioning}
KEY MESSAGES: {key_messages}
PERSONA OBJECTIONS: {objections}

OUTPUT FORMAT (return ONLY this JSON in `design_spec`):
{{
  "zones": [
    {{ "id": "competitor_header", "type": "hero", "content": {{ "text": "vs {competitor}" }} }},
    {{ "id": "our_strengths", "type": "comparison_grid", "content": {{ "items": ["Strength 1", "Strength 2"] }} }},
    {{ "id": "objections", "type": "objection_list", "content": {{ "items": ["Objection → Response 1", "Objection → Response 2"] }} }},
    {{ "id": "proof_block", "type": "proof_block", "content": {{ "items": ["Proof 1", "Proof 2", "Proof 3"] }} }}
  ]
}}

RULES:
- competior_header.text MUST include competitor name
- comparison_grid shows our strengths vs theirs (3-4 items)
- objection_list shows verbatim objections with responses (max 5)
- proof_block shows top 3 proof points with stats
- All objection responses MUST be from the graph (verbatim)""",
        "prefab_template": "battlecard_visual",
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