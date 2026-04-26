"""MsgStack MCP Server entry point."""

import os
from typing import Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

from src.grounding import tools as grounding_tools
from src.grounding.session import reset_session
from src.store import Store

load_dotenv()

mcp = FastMCP("MsgStack")


@mcp.tool()
def search_messaging(
    query: str,
    section_types: Optional[list[str]] = None,
    personas: Optional[list[str]] = None,
    channels: Optional[list[str]] = None,
    message_houses: Optional[list[str]] = None,
    include_variants: bool = True,
    min_priority: Optional[int] = None,
) -> dict:
    """Search marketing messaging frameworks for grounding content.

    Provide a natural language query and optional filters to retrieve relevant
    messaging chunks from your brand's messaging libraries. Use this before
    generating any marketing content to ensure it aligns with approved messaging.

    Args:
        query: What messaging content are you looking for? Include section types,
               personas, and channels naturally (e.g., "headlines for CTOs on LinkedIn").
        section_types: Filter by message type: headline, subhead, benefit, proof_point,
                      objection, social_proof, positioning.
        personas: Filter by specific audience personas (e.g., SMB CTO, FinOps Manager).
        channels: Filter by channel: linkedin, email, landing, paid, twitter, blog.
        message_houses: Restrict to specific message houses by ID.
        include_variants: Include channel-specific message variants in results.
        min_priority: Only return messages at or above this priority (1=highest).

    Returns:
        Matched messaging chunks with confidence scores and grounding context.
    """
    return grounding_tools.search_messaging(
        query=query,
        section_types=section_types,
        personas=personas,
        channels=channels,
        message_houses=message_houses,
        include_variants=include_variants,
        min_priority=min_priority,
    ).model_dump()


@mcp.tool()
def set_active_house(house_id: str) -> dict:
    """Pin a message house as the active grounding context for the session.

    Subsequent searches will default to this house unless overridden.
    Call this first when you know which messaging framework to use.
    """
    return grounding_tools.set_active_house(house_id)


@mcp.tool()
def get_message_house(
    house_id: Optional[str] = None,
    house_name: Optional[str] = None,
) -> dict:
    """Retrieve a full message house with all key messages, personas, and positioning.

    Returns all content: positioning statement, tagline, differentiation, key messages
    by section type, and full persona profiles.

    Args:
        house_id: UUID of the message house.
        house_name: Name of the message house (alternative to house_id).
    """
    return grounding_tools.get_message_house(house_id, house_name, ["all"])


@mcp.tool()
def list_message_houses(query: Optional[str] = None) -> dict:
    """List all available messaging frameworks.

    Args:
        query: Optional text search across house names and summaries.
    """
    return grounding_tools.list_message_houses(query)


@mcp.tool()
def compare_houses(house_ids: list[str]) -> dict:
    """Compare two or more message houses side by side.

    Useful for cross-quarter positioning changes or multi-brand scenarios.
    """
    return grounding_tools.compare_houses(house_ids)


@mcp.tool()
def get_grounding_context() -> dict:
    """Get the current grounding context for this session.

    Returns which house is active, which personas are in scope, and which
    chunks have been used so far.
    """
    return grounding_tools.get_grounding_context().model_dump()


def _resolve_house(store, house_id: Optional[str], house_name: Optional[str] = None):
    """Resolve a message house by ID (UUID) or name, with fallback."""
    from uuid import UUID as _UUID
    house = None
    if house_id:
        try:
            house = store.get_house(_UUID(house_id))
        except (ValueError, AttributeError):
            pass
    if house is None and house_name:
        house = store.get_house_by_name(house_name)
    if house is None and house_id:
        house = store.get_house_by_name(house_id)
    return house


@mcp.tool()
def generate_one_pager(messaging_house_id: str) -> dict:
    """Generate a structured messaging one-pager from a message house.

    Returns positioning, tagline, key messages by section, and personas
    in a structured format — present this as a formatted document to the user.

    Args:
        messaging_house_id: UUID or name of the message house.
    """
    store = Store()
    store.init()
    house = _resolve_house(store, messaging_house_id)
    if not house:
        return {"error": f"House not found. Use list_message_houses to find valid IDs."}

    messages = store.get_key_messages(house.id)
    personas = store.get_personas(house.id)

    grouped = {}
    for m in messages:
        key = str(m.section_type)
        grouped.setdefault(key, []).append(m.content)

    return {
        "house_name": house.name,
        "tagline": house.tagline,
        "positioning": house.positioning,
        "differentiation": house.differentiation,
        "audience": house.audience,
        "key_messages": grouped,
        "personas": [{"name": p.name, "description": p.description, "pain_points": p.pain_points} for p in personas],
        "message_count": len(messages),
    }


@mcp.tool()
def generate_social_posts(
    messaging_house_id: str,
    channels: Optional[list[str]] = None,
) -> dict:
    """Get social media post variants from a message house.

    Returns pre-written LinkedIn/social variants stored in the message house.
    Use generate_artifact with skill_id='linkedin_post' for LLM-generated posts.

    Args:
        messaging_house_id: UUID or name of the message house.
        channels: Which channels: linkedin, twitter, email, etc.
    """
    store = Store()
    store.init()
    house = _resolve_house(store, messaging_house_id)
    if not house:
        return {"error": "House not found. Use list_message_houses."}

    messages = store.get_key_messages(house.id)
    target_channels = channels or ["linkedin"]
    posts = []
    for m in messages:
        for channel in target_channels:
            variant = (m.variants or {}).get(channel)
            if variant:
                posts.append({
                    "channel": channel,
                    "section_type": str(m.section_type),
                    "content": variant,
                    "priority": m.priority,
                })

    return {
        "house_name": house.name,
        "posts": posts,
        "note": "These are pre-written channel variants. Use generate_artifact(skill_id='linkedin_post') for fresh LLM-generated posts.",
    }


@mcp.tool()
def generate_email_template(
    messaging_house_id: str,
    stage: str = "awareness",
) -> dict:
    """Generate an email template grounded in the message house.

    Uses LLM to create a subject line, hook, body, and CTA for the funnel stage.
    Returns the template content directly — present it to the user as a formatted email.

    Args:
        messaging_house_id: UUID or name of the message house.
        stage: Funnel stage: awareness, consideration, or decision.
    """
    from src.pipeline.generator import ArtifactGenerator
    from src.pipeline.skills import SkillManager

    store = Store()
    store.init()
    house = _resolve_house(store, messaging_house_id)
    if not house:
        return {"error": "House not found. Use list_message_houses."}

    skills = SkillManager()
    generator = ArtifactGenerator(store, skills)
    artifact = generator.generate("email_template", str(house.id), {"stage": stage})
    return {
        "skill_id": "email_template",
        "stage": stage,
        "house_name": artifact.house_name,
        "sections": artifact.sections,
        "raw_content": artifact.raw_content,
    }


@mcp.tool()
def generate_artifact(
    skill_id: str,
    house_id: Optional[str] = None,
    house_name: Optional[str] = None,
    custom_context: Optional[dict] = None,
) -> str:
    """Generate a marketing artifact grounded in a message house.

    Returns the complete artifact text. Display it in full to the user —
    do not summarize or paraphrase it.

    Args:
        skill_id: The artifact type: one_pager, linkedin_post, email_template,
                  battlecard, press_release, blog_post, faq_document
        house_id: UUID of the message house (from list_message_houses).
        house_name: Name of the message house (alternative to house_id).
        custom_context: Optional extra context for the prompt (e.g. event details).
    """
    from src.pipeline.generator import ArtifactGenerator
    from src.pipeline.skills import SkillManager

    store = Store()
    store.init()

    house = None
    if house_id:
        try:
            from uuid import UUID as _UUID
            house = store.get_house(_UUID(house_id))
        except (ValueError, AttributeError):
            house = None
    if house is None and house_name:
        house = store.get_house_by_name(house_name)
    if house is None and house_id and not house_name:
        house = store.get_house_by_name(house_id)
    if house is None:
        all_houses = store.list_houses()
        names = ", ".join(h.name for h in all_houses)
        return f"House not found. Available houses: {names}"

    skills = SkillManager()
    generator = ArtifactGenerator(store, skills)
    artifact = generator.generate(skill_id, str(house.id), custom_context or {})
    return artifact.raw_content


@mcp.tool()
def build_ui_artifact(
    artifact_type: str,
    house_id: Optional[str] = None,
    house_name: Optional[str] = None,
    stage: Optional[str] = None,
    channels: Optional[list[str]] = None,
) -> str:
    """Build a visual UI artifact and return a public URL to open it in a browser.

    Present the URL as a clickable link. The page renders a full interactive
    Prefab UI with messaging cards, personas, and action buttons.

    Args:
        artifact_type: one_pager | social_posts | email_template
        house_id: UUID of the message house.
        house_name: Name of the message house (alternative to house_id).
        stage: For email_template only: awareness | consideration | decision
        channels: For social_posts only: e.g. ["linkedin"]
    """
    store = Store()
    store.init()
    house = _resolve_house(store, house_id, house_name)
    if not house:
        all_houses = store.list_houses()
        return "House not found. Available: " + ", ".join(h.name for h in all_houses)

    valid_types = ["one_pager", "social_posts", "email_template"]
    if artifact_type not in valid_types:
        return f"Unknown artifact_type. Choose: {', '.join(valid_types)}"

    base_url = os.environ.get("MSGSTACK_BASE_URL", "http://localhost:8001")
    params = ""
    if artifact_type == "email_template" and stage:
        params = f"?stage={stage}"
    elif artifact_type == "social_posts" and channels:
        params = f"?channels={','.join(channels)}"

    url = f"{base_url}/artifact/{artifact_type}/{house.id}{params}"
    return f"Open the {artifact_type.replace('_', ' ')} for **{house.name}**: {url}"


@mcp.tool()
def list_skills() -> dict:
    """List all available artifact skills."""
    from src.pipeline.skills import SkillManager
    skills = SkillManager()
    return {"skills": skills.list_skills()}


@mcp.tool()
def reset_conversation() -> dict:
    """Reset the grounding session context.

    Clears the active house, recent searches, and used chunks.
    Use when starting a new topic or switching message houses.
    """
    reset_session()
    return {"message": "Session reset. No active message house."}


@mcp.tool()
def get_framework_spec() -> dict:
    """Return the specification for a complete MsgStack messaging framework.

    Use this to understand what a fully-populated message house should contain:
    required fields, section types, message counts, persona structure, and
    channel variants. Also returns a completeness checklist.
    """
    from src.models import COMPLETE_FRAMEWORK_SPEC
    return COMPLETE_FRAMEWORK_SPEC


@mcp.tool()
def check_framework_completeness(house_id: Optional[str] = None, house_name: Optional[str] = None) -> dict:
    """Check how complete a message house is against the framework spec.

    Returns a completeness report with what's present, what's missing, and a score.

    Args:
        house_id: UUID of the message house.
        house_name: Name of the message house (alternative to house_id).
    """
    from src.models import COMPLETE_FRAMEWORK_SPEC, SectionType

    store = Store()
    store.init()
    house = _resolve_house(store, house_id, house_name)
    if not house:
        return {"error": "House not found. Use list_message_houses to find valid IDs."}

    messages = store.get_key_messages(house.id)
    personas = store.get_personas(house.id)

    by_section = {}
    for m in messages:
        key = str(m.section_type)
        by_section.setdefault(key, []).append(m)

    checks = []
    passed = 0
    total = 0

    def check(label, condition):
        nonlocal passed, total
        total += 1
        result = bool(condition)
        if result:
            passed += 1
        checks.append({"check": label, "passed": result})

    check("Positioning field filled (50+ chars)", len(house.positioning or "") >= 50)
    check("Tagline present and under 60 chars", bool(house.tagline) and len(house.tagline) < 60)
    check("Differentiation is specific (30+ chars)", len(house.differentiation or "") >= 30)
    check("Audience defined", bool(house.audience))
    check("Brand personality defined", bool(house.brand_personality))

    required_min = {"headline": 3, "subhead": 3, "benefit": 3, "proof_point": 3, "objection": 3, "social_proof": 3, "positioning": 1}
    for section, min_count in required_min.items():
        msgs = by_section.get(section, [])
        check(f"{section}: {min_count}+ messages (has {len(msgs)})", len(msgs) >= min_count)

    check("2+ personas defined", len(personas) >= 2)
    for p in personas[:3]:
        check(f"Persona '{p.name}': pain_points defined", bool(p.pain_points))
        check(f"Persona '{p.name}': buying_triggers defined", bool(p.buying_triggers))
        check(f"Persona '{p.name}': objections defined", bool(p.objections))

    msgs_with_linkedin = sum(1 for m in messages if (m.variants or {}).get("linkedin"))
    msgs_with_email = sum(1 for m in messages if (m.variants or {}).get("email"))
    check(f"LinkedIn variants on 5+ messages (has {msgs_with_linkedin})", msgs_with_linkedin >= 5)
    check(f"Email variants on 5+ messages (has {msgs_with_email})", msgs_with_email >= 5)

    score = round((passed / total) * 100) if total else 0

    return {
        "house_name": house.name,
        "score": score,
        "passed": passed,
        "total": total,
        "checks": checks,
        "missing": [c["check"] for c in checks if not c["passed"]],
        "message_count": len(messages),
        "persona_count": len(personas),
        "sections_covered": list(by_section.keys()),
    }


@mcp.tool()
def seed_database() -> dict:
    """Seed the database with sample messaging content.

    Loads a realistic B2B SaaS messaging house for testing.
    """
    from seed_data.seed import seed as run_seed
    run_seed()
    return {"message": "Database seeded with sample messaging content."}


def main():
    store = Store()
    store.init()
    mcp.run()


if __name__ == "__main__":
    main()