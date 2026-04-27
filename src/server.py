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
    min_confidence: Optional[float] = None,
    workspace_id: Optional[str] = None,
) -> dict:
    """Search marketing messaging frameworks for grounding content.

    Provide a natural language query and optional filters to retrieve relevant
    messaging chunks from your brand's messaging libraries. Use this before
    generating any marketing content to ensure it aligns with approved messaging.

    Args:
        query: What messaging content are you looking for? Include section types,
               personas, and channels naturally (e.g., "headlines for CTOs on LinkedIn").
        section_types: Filter by message type: headline, subhead, benefit, use_case,
                      proof_point, objection, social_proof, positioning, know_your_market.
        personas: Filter by specific audience personas (e.g., SMB CTO, FinOps Manager).
        channels: Filter by channel: linkedin, email, landing, paid, twitter, blog.
        message_houses: Restrict to specific message houses by ID.
        include_variants: Include channel-specific message variants in results.
        min_priority: Only return messages at or above this priority (1=highest).
        min_confidence: Warn if average result confidence is below this threshold (0.0–1.0).
        workspace_id: Filter to a specific workspace (optional).

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
        min_confidence=min_confidence,
        workspace_id=workspace_id,
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
    """Retrieve full content of a messaging framework for research.

    Use this tool to understand the brand positioning, audience, and key messages.
    
    CRITICAL: Do NOT use the data returned here to manually write a one-pager or 
    artifact for the user. Instead, use 'generate_artifact' or 'build_ui_artifact'.

    Args:
        house_id: UUID of the message house.
        house_name: Name of the message house (alternative to house_id).
    """
    return grounding_tools.get_message_house(house_id, house_name, ["all"])


@mcp.tool()
def list_message_houses(query: Optional[str] = None, workspace_id: Optional[str] = None) -> dict:
    """List all available message houses with their IDs and summaries.

    Call this FIRST whenever the user mentions a brand, product, or company
    name — before calling any generate or search tool. Use the returned
    house_id (UUID) for all subsequent tool calls.

    Args:
        query: Optional text search across house names and summaries.
        workspace_id: Filter to a specific workspace (optional).
    """
    return grounding_tools.list_message_houses(query, workspace_id)


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


def generate_one_pager_data(messaging_house_id: str) -> dict:
    """Internal helper to get structured data for a one-pager."""
    store = Store()
    store.init()
    house = _resolve_house(store, messaging_house_id)
    if not house:
        return {"error": f"House not found."}

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
def generate_artifact(
    skill_id: str,
    house_id: Optional[str] = None,
    house_name: Optional[str] = None,
    custom_context: Optional[dict] = None,
) -> str:
    """MANDATORY tool for generating any marketing copy (One-Pager, Email, Post, etc).

    USE THIS TOOL whenever the user asks to "generate", "write", "create", or "draft" 
    a document. DO NOT attempt to write the document yourself based on house data.

    Args:
        skill_id: The type of content to generate. MUST be one of the IDs 
                  returned by list_skills (e.g., 'one_pager', 'linkedin_post', 
                  'email_template', 'battlecard').
        house_id: UUID of the message house (preferred).
        house_name: Exact name of the message house.
        custom_context: Optional context like {"stage": "decision", "competitor": "X"}.
    """
    from src.pipeline.generator import ArtifactGenerator
    from src.pipeline.skills import SkillManager
    from src.grounding.session import get_session

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
        return f"House not found. Call list_message_houses to see valid options. Available: {names}"

    skills = SkillManager()
    generator = ArtifactGenerator(store, skills)
    artifact = generator.generate(skill_id, str(house.id), custom_context or {})

    # Record in grounding session so get_grounding_context reflects this
    session = get_session()
    workspace_id = store.get_house_workspace_id(house.id) or "default"
    session.set_active_house(
        house_id=house.id,
        house_name=house.name,
        house_summary=house.summary or "",
        personas=[],
        workspace_id=workspace_id,
    )

    # Automatically append a visual link if this artifact type supports a UI view
    # Supported skills: one_pager, linkedin_post, email_template, battlecard, 
    # blog_post, press_release, faq_document, talk_track, objection_handler, 
    # event_brief, executive_summary, partner_brief
    
    base_url = os.environ.get("MSGSTACK_BASE_URL", "http://localhost:8001")
    url = f"{base_url}/artifact/{skill_id}/{house.id}"
    
    # Add stage/channel context to URL if available
    if custom_context:
        params = []
        if skill_id == "email_template" and "stage" in custom_context:
            params.append(f"stage={custom_context['stage']}")
        elif skill_id == "linkedin_post" and "channels" in custom_context:
            ch = custom_context["channels"]
            params.append(f"channels={','.join(ch) if isinstance(ch, list) else ch}")
        if params:
            url += "?" + "&".join(params)

    content = artifact.raw_content
    content += f"\n\n---\n\n**Visual Version:** {url}"

    return content


@mcp.tool()
def build_ui_artifact(
    artifact_type: str,
    house_id: Optional[str] = None,
    house_name: Optional[str] = None,
    stage: Optional[str] = None,
    channels: Optional[list[str]] = None,
) -> str:
    """Generate a visual/HTML link for a marketing artifact.

    USE THIS TOOL when the user wants a "link", "page", "visual version", 
    or "web view" of an artifact.

    Args:
        artifact_type: one_pager | social_posts | email_template
        house_id: UUID of the message house (optional if house_name provided).
        house_name: Exact name of the message house.
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
    """List all available marketing artifact types (skills).

    Use this to see what kinds of documents you can generate for a user.
    Each skill returned can be used as 'skill_id' in 'generate_artifact'.
    """
    from src.pipeline.skills import SkillManager
    skills = SkillManager()
    return {
        "available_artifacts": [
            {
                "id": s["id"],
                "name": s["name"],
                "description": s["description"],
                "recommended_for": s.get("channels", ["all"])
            }
            for s in skills.list_skills()
        ]
    }


@mcp.tool()
def list_mcp_tools() -> dict:
    """List all available MCP tools in this server with their descriptions.
    
    Use this to understand the full capabilities of MsgStack, including
    grounding, research, generation, and visual artifact creation.
    """
    tool_defs = [
        {"name": "search_messaging", "description": "Search messaging frameworks for grounding content (headlines, proof points, etc)."},
        {"name": "list_message_houses", "description": "List all available messaging frameworks/brands."},
        {"name": "get_message_house", "description": "Retrieve full framework content for deep research (positioning, personas)."},
        {"name": "list_skills", "description": "List all 12+ types of marketing artifacts you can generate (Email, PR, Blog, etc)."},
        {"name": "generate_artifact", "description": "MANDATORY: Generate a full document draft with an automatic visual link."},
        {"name": "build_ui_artifact", "description": "Get a visual HTML link for a specific framework artifact."},
        {"name": "set_active_house", "description": "Focus the session on a specific brand framework."},
        {"name": "check_framework_completeness", "description": "Audit a framework for missing critical messaging sections."},
        {"name": "get_framework_spec", "description": "See the requirements for a 'Perfect' messaging house."},
        {"name": "seed_database", "description": "Reset or load sample B2B SaaS data."},
    ]
    return {"tools": tool_defs}


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