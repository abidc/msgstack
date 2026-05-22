"""MsgStack MCP Server entry point."""

import os
from typing import Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

from src.grounding import tools as grounding_tools
from src.grounding.session import reset_session
from src.store import Store, get_store

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
    retrieval_mode: Optional[str] = None,
    limit: Optional[int] = None,
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
        retrieval_mode: "hybrid" (default), "vector", "graph" (deterministic — bypasses
                        vector approximation, returns exact approved content), or "keyword".
        limit: Maximum number of results to return (default: no cap). Set to 5–10 to
               avoid flooding the context window.

    Returns:
        Matched messaging chunks with confidence scores and grounding context.
    """
    result = grounding_tools.search_messaging(
        query=query,
        section_types=section_types,
        personas=personas,
        channels=channels,
        message_houses=message_houses,
        include_variants=include_variants,
        min_priority=min_priority,
        min_confidence=min_confidence,
        workspace_id=workspace_id,
        retrieval_mode=retrieval_mode or "hybrid",
    ).model_dump()
    if limit and "results" in result:
        result["results"] = result["results"][:limit]
    return result


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

    IMPORTANT: The 'summary' in the response is a 2–3 sentence overview ONLY.
    It does NOT contain the actual key messages, headlines, or proof points.
    After identifying the house_id:
    - To GENERATE a document → call generate_artifact(skill_id, house_id)
    - To READ full messaging content → call get_message_house(house_id)
    Never write marketing content yourself using only this tool's output.

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
    store = get_store()
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
    """Generate marketing content from a message house framework using an AI skill.

    CALL THIS TOOL IMMEDIATELY — do not explain, do not show code, do not ask for confirmation —
    whenever the user says anything like: "generate", "create", "write", "build", "make", "draft",
    "give me", "show me", "produce", or "put together" followed by any of:
    one-pager, one pager, datasheet, battlecard, battle card, email, LinkedIn post, blog post,
    press release, FAQ, talk track, objection handler, executive summary, partner brief, event brief,
    or any other marketing document or copy.

    You can pass house_name instead of house_id — no prior lookup needed.
    NEVER write the content yourself. ALWAYS call this tool instead.

    The tool runs the AI generator and returns the full content PLUS a canvas visual link.
    For battlecard, you MUST also pass custom_context={"competitor": "<name>"}.
    For email_template, optionally pass custom_context={"stage": "awareness|consideration|decision"}.

    Args:
        skill_id: Content type — one of: one_pager, linkedin_post, email_template,
                  battlecard, press_release, blog_post, faq_document, talk_track,
                  objection_handler, event_brief, executive_summary, partner_brief.
        house_id: UUID of the message house (preferred over house_name).
        house_name: Exact name of the message house (used if house_id not available).
        custom_context: Extra context dict, e.g. {"competitor": "Salesforce"} for battlecard
                        or {"stage": "decision"} for email_template.
    """
    from src.pipeline.generator import ArtifactGenerator
    from src.pipeline.skills import SkillManager
    from src.grounding.session import get_session

    store = get_store()

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

    skills = SkillManager(skills_dir="data/skills")

    # Check required context inputs before running the generator
    from src.pipeline.skills import SKILL_CONTEXT_INPUTS
    required_inputs = SKILL_CONTEXT_INPUTS.get(skill_id, [])
    provided = custom_context or {}
    missing = [inp for inp in required_inputs if inp.get("required") and inp["key"] not in provided]
    if missing:
        labels = " and ".join(f'"{inp["label"]}"' for inp in missing)
        example = {inp["key"]: inp.get("placeholder", f"<{inp['label']}>") for inp in missing}
        return (
            f'To generate a {skill_id.replace("_", " ")}, I need {labels}. '
            f'Please provide it via `custom_context`, e.g. `{{"custom_context": {example}}}`.'
        )

    generator = ArtifactGenerator(store, skills)
    artifact = generator.generate(skill_id, str(house.id), provided)

    try:
        saved = store.save_artifact(
            house_id=house.id,
            skill_id=skill_id,
            house_name=artifact.house_name,
            sections=artifact.sections,
            raw_content=artifact.raw_content,
        )
        artifact_history_id = saved["id"]
    except Exception:
        artifact_history_id = None

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

    base_url = os.environ.get("MSGSTACK_BASE_URL", "http://localhost:8001")
    
    content = artifact.raw_content
    url = None
    
    if artifact_history_id:
        if artifact.renderer_type == "fabric":
            url = f"{base_url}/canvas?artifact_id={artifact_history_id}"
        elif artifact.renderer_type == "reveal":
            url = f"{base_url}/presentation/{artifact_history_id}"
            
    if not url and artifact.renderer_type not in ("fabric", "reveal"):
        visual_types = {"one_pager", "social_posts", "email_template", "battlecard", "email_sequence"}
        skill_config = skills.get_skill(skill_id)
        artifact_type = skill_config.get("prefab_template", skill_id) if skill_config else skill_id
        
        if artifact_type in visual_types:
            url = f"{base_url}/artifact/{artifact_type}/{house.id}"
            params = []
            if skill_id == "battlecard" and provided.get("competitor"):
                params.append(f"competitor={provided['competitor']}")
            elif skill_id == "email_template" and provided.get("stage"):
                params.append(f"stage={provided['stage']}")
            elif skill_id in ("social_posts", "linkedin_post") and provided.get("channels"):
                ch = provided["channels"]
                params.append(f"channels={','.join(ch) if isinstance(ch, list) else ch}")
            if params:
                url += "?" + "&".join(params)
                
    if url:
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
    """Return a visual HTML page URL for a message house — does NOT run the AI generator.

    Use this ONLY when the user asks for a "link", "page", "visual", or "web view"
    of a framework that already exists — NOT to generate new content.

    To actually generate content (one-pager, email, battlecard, etc.), use
    generate_artifact instead.

    Args:
        artifact_type: one_pager | social_posts | email_template | battlecard
        house_id: UUID of the message house (preferred).
        house_name: Exact name of the message house.
        stage: For email_template only: awareness | consideration | decision
        channels: For social_posts only: e.g. ["linkedin"]
    """
    store = get_store()
    house = _resolve_house(store, house_id, house_name)
    if not house:
        all_houses = store.list_houses()
        return "House not found. Available: " + ", ".join(h.name for h in all_houses)

    valid_types = ["one_pager", "social_posts", "email_template", "battlecard"]
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
    skills = SkillManager(skills_dir="data/skills")
    return {
        "available_artifacts": [
            {
                "id": s["id"],
                "name": s["name"],
                "description": s["description"],
                "recommended_for": s.get("channels", ["all"]),
                "requires_context": {
                    "battlecard": {"competitor": "Competitor name (required)"},
                    "blog_post": {"topic": "Blog topic (required)"},
                    "press_release": {"announcement": "Announcement summary (required)"},
                    "event_brief": {"event_name": "Event name (required)"},
                    "email_template": {"stage": "awareness|consideration|decision (optional)"},
                }.get(s["id"], {}),
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
        {"name": "export_to_penpot", "description": "Export a MsgStack artifact to Penpot design file and return the edit link."},
        {"name": "set_penpot_project", "description": "Link a Penpot project to a MsgStack workspace for design sync."},
    ]
    return {"tools": tool_defs}


@mcp.tool()
def export_to_penpot(
    artifact_id: str,
    workspace_id: str,
    house_id: str,
) -> dict:
    """Export a MsgStack artifact to Penpot and return the edit link.

    Creates a fully designed Penpot file with frames, text layers,
    brand colors, and proper layout matching the artifact's design spec.

    Args:
        artifact_id: The artifact ID to export.
        workspace_id: The workspace ID (to find the linked Penpot project).
        house_id: The message house ID (to get brand tokens and messages).

    Returns:
        dict with file_id, edit_url, and creation status.
    """
    return grounding_tools.export_to_penpot(artifact_id, workspace_id, house_id)


@mcp.tool()
def set_penpot_project(workspace_id: str, project_id: str) -> dict:
    """Link a Penpot project to a MsgStack workspace.

    Args:
        workspace_id: The MsgStack workspace ID.
        project_id: The Penpot project ID to link.

    Returns:
        dict with status and confirmation.
    """
    return grounding_tools.set_penpot_project(workspace_id, project_id)


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

    store = get_store()
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

    # Generate actionable recommendations for failing checks
    recommendations = []
    for c in checks:
        if not c["passed"]:
            label = c["check"]
            if "Positioning" in label:
                recommendations.append("Expand the positioning statement to be more specific (50+ characters).")
            elif "Tagline" in label:
                recommendations.append("Add a tagline under 60 characters that captures the core value proposition.")
            elif "Differentiation" in label:
                recommendations.append("Fill in the differentiation field with a concrete competitive advantage.")
            elif "Audience" in label:
                recommendations.append("Define the primary target audience in the house metadata.")
            elif "Brand personality" in label:
                recommendations.append("Add brand personality traits (e.g., bold, empathetic, technical).")
            elif "personas" in label.lower():
                recommendations.append("Define at least 2 distinct buyer personas with pain points and triggers.")
            elif "LinkedIn" in label:
                recommendations.append("Add LinkedIn channel variants to at least 5 key messages.")
            elif "Email" in label:
                recommendations.append("Add email channel variants to at least 5 key messages.")
            else:
                # section-level check: extract section name
                section = label.split(":")[0].strip()
                recommendations.append(f"Add more {section} messages (minimum required not met).")

    return {
        "house_name": house.name,
        "score": score,
        "passed": passed,
        "total": total,
        "checks": checks,
        "missing": [c["check"] for c in checks if not c["passed"]],
        "recommendations": recommendations,
        "message_count": len(messages),
        "persona_count": len(personas),
        "sections_covered": list(by_section.keys()),
    }


@mcp.tool()
def get_graph_connections(
    house_id: str,
    persona: Optional[str] = None,
    channel: Optional[str] = None,
) -> dict:
    """Retrieve verbatim approved messaging via deterministic graph traversal.

    Unlike search_messaging (which uses vector approximation), this tool queries
    the knowledge graph directly — returning exactly the content associated with
    a house, persona, or channel via typed relationships. Use this when you need:
    - An exact approved tagline or headline (not the nearest neighbor)
    - All messages that apply to a specific persona
    - All messages approved for a specific channel

    Args:
        house_id: UUID of the message house to query.
        persona: Optional persona name to filter by ADDRESSES relationship.
        channel: Optional channel to filter by APPLIES_TO relationship.

    Returns:
        List of content chunks retrieved via graph traversal (confidence=1.0).
    """
    from src.grounding.graph import get_graph_engine
    engine = get_graph_engine()
    chunks = engine.get_connections(house_id, persona=persona, channel=channel)
    return {
        "retrieval_mode": "graph",
        "house_id": house_id,
        "persona_filter": persona,
        "channel_filter": channel,
        "count": len(chunks),
        "chunks": [{"content": c.get("content", ""), "section_type": c.get("section_type", ""),
                    "priority": c.get("priority", 3)} for c in chunks],
    }


@mcp.tool()
def list_channels() -> dict:
    """List all available messaging channels (including user-defined custom channels).

    Returns the full channel registry — both the default channels (email, linkedin,
    twitter, etc.) and any custom channels added by the team. Use channel IDs as
    the 'channels' filter in search_messaging or get_graph_connections.
    """
    store = get_store()
    return {"channels": store.get_channels()}




# ── MCP Prompts ──────────────────────────────────────────────────────────────
# Clients that support prompts/list (OpenWebUI, Claude Desktop, etc.) will
# discover these and can inject them as system messages automatically.

@mcp.prompt()
def system_instructions() -> str:
    """Complete operating guide for MsgStack tools. Inject at conversation start."""
    return """You are connected to MsgStack, a marketing messaging intelligence server.

## Tool Selection Rules

**GENERATE content** — call `generate_artifact` immediately. NEVER write the content yourself.
Triggers: "build", "make", "create", "generate", "write", "draft", "give me", "show me",
"put together", "can you make" + any of: one-pager, battlecard, email, LinkedIn post,
blog post, press release, FAQ, talk track, objection handler, executive summary,
partner brief, event brief, or any other marketing document.

**SEARCH for messaging** — call `search_messaging` when:
- User asks what messaging exists for a topic, persona, or channel
- You need grounding before writing any copy yourself
- User asks for headlines, proof points, objections, or talking points

**LIST / BROWSE** — use `list_message_houses` when the user hasn't specified a framework,
and `list_skills` when they haven't specified an artifact type.

**RESEARCH a framework** — call `get_message_house` when the user wants to understand
a brand's positioning, personas, or full messaging structure.

## Output Rules

- When `generate_artifact` returns content, paste it **verbatim and in full**. Do not
  summarize, paraphrase, or describe it. The user wants the actual document.
- When `search_messaging` returns results, quote the messaging chunks directly.
- Always include visual links when returned by the tool.

## Standard Generation Workflow

1. If no framework is specified → call `list_message_houses` and ask the user to pick one.
2. If no artifact type is specified → call `list_skills` and ask which they want.
3. Call `generate_artifact` with `skill_id` + `house_id` (+ `custom_context` if needed).
4. Paste the full returned content. Done.

## Required context_inputs per skill

- battlecard: `custom_context={"competitor": "<name>"}` — REQUIRED
- blog_post: `custom_context={"topic": "<topic>"}` — REQUIRED
- press_release: `custom_context={"announcement": "<summary>"}` — REQUIRED
- event_brief: `custom_context={"event_name": "<name>"}` — REQUIRED
- email_template: `custom_context={"stage": "awareness|consideration|decision"}` — optional

## When to use get_graph_connections vs search_messaging

- Use `get_graph_connections` when you need **exact, verbatim approved content** — locked taglines,
  specific proof points, or all messages for a persona. Confidence is always 1.0 (no approximation).
- Use `search_messaging` for **exploratory or semantic queries** where you want the closest match
  to a natural language request. Use `retrieval_mode="graph"` as a shortcut for the same effect.
"""


@mcp.prompt()
def quick_start() -> str:
    """One-paragraph quick-start guide shown to users new to MsgStack."""
    return """MsgStack gives you AI-generated marketing artifacts grounded in your brand messaging.

Call `list_message_houses` to see available frameworks, then use the returned house_id for all other tools.

**To generate a document**, just say what you want and which brand, e.g.:
- "Write a one-pager for [framework name]"
- "Build a battlecard for [framework name] vs [competitor]"
- "Draft a LinkedIn post for [framework name]"

Available artifact types: one-pager, battlecard, email template, LinkedIn post, blog post,
press release, FAQ, talk track, objection handler, executive summary, partner brief, event brief.
"""


def main():
    mcp.run()


if __name__ == "__main__":
    main()