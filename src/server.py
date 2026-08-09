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
def search_assertions(
    query: str,
    assertion_types: Optional[list[str]] = None,
    audiences: Optional[list[str]] = None,
    channels: Optional[list[str]] = None,
    specs: Optional[list[str]] = None,
    include_variants: bool = True,
    min_priority: Optional[int] = None,
    min_confidence: Optional[float] = None,
    workspace_id: Optional[str] = None,
    retrieval_mode: Optional[str] = None,
    limit: Optional[int] = None,
    include_unapproved: bool = False,
    department: Optional[str] = None,
) -> dict:
    """Search approved spec graph entries for grounding content.

    By default only returns entries with status APPROVED or LOCKED.
    Use include_unapproved=True to include DRAFT and IN_REVIEW entries.
    OUTDATED entries are always excluded.

    Provide a natural language query and optional filters to retrieve relevant
    assertions from your organization's specs. Use this before
    generating or verifying content to ensure it aligns with approved truth.

    Args:
        query: What spec content are you looking for? Include section types,
               audiences, and channels naturally (e.g., "headlines for CTOs on LinkedIn").
        assertion_types: Filter by entry type: headline, subhead, benefit, use_case,
                      proof_point, qa_pair, social_proof, positioning, know_your_market.
        audiences: Filter by specific audience audiences (e.g., SMB CTO, FinOps Manager).
        channels: Filter by target destination channel: linkedin, email, landing, paid, twitter, blog.
        specs: Restrict to specific specs by ID or name.
        include_variants: Include channel-specific variant rewrites in results.
        min_priority: Only return entries at or above this priority (1=highest).
        min_confidence: Warn if average result confidence is below this threshold (0.0–1.0).
        workspace_id: Filter to a specific workspace (optional).
        retrieval_mode: "hybrid" (default), "vector", "graph" (deterministic — bypasses
                        vector approximation, returns exact approved content), or "keyword".
        limit: Maximum number of results to return (default: no cap). Set to 5–10 to
               avoid flooding the context window.
        include_unapproved: If True, also return DRAFT and IN_REVIEW entries.
        department: Filter to a specific department (optional).

    Returns:
        Matched assertions with confidence scores and grounding context.
    """
    result = grounding_tools.search_assertions(
        query=query,
        assertion_types=assertion_types,
        audiences=audiences,
        channels=channels,
        specs=specs,
        include_variants=include_variants,
        min_priority=min_priority,
        min_confidence=min_confidence,
        workspace_id=workspace_id,
        retrieval_mode=retrieval_mode or "hybrid",
        include_unapproved=include_unapproved,
    ).model_dump()

    # Filter by department if provided
    if department and "results" in result:
        store = get_store()
        filtered_results = []
        for r in result["results"]:
            domain_id = r.get("source", {}).get("spec_id") or r.get("source", {}).get("spec_id")
            if domain_id:
                from uuid import UUID
                try:
                    domain = store.get_spec(UUID(str(domain_id)))
                    if domain and domain.department.lower() == department.lower():
                        filtered_results.append(r)
                except Exception:
                    pass
        result["results"] = filtered_results

    if limit and "results" in result:
        result["results"] = result["results"][:limit]
    
    # Align terminology in output keys
    if "results" in result:
        for r in result["results"]:
            if "spec_name" in r:
                r["spec_name"] = r["spec_name"]
            if "spec_summary" in r:
                r["spec_summary"] = r["spec_summary"]
            if "spec_id" in r:
                r["spec_id"] = r["spec_id"]
            if "assertion_id" in r:
                r["assertion_id"] = r["assertion_id"]

    return result


@mcp.tool()
def set_active_spec(domain_id: str) -> dict:
    """Pin a spec as the active grounding context for the session.

    Subsequent searches will default to this domain unless overridden.
    Call this first when you know which spec to use.
    """
    res = grounding_tools.set_active_spec(domain_id)
    # Align terminology in output
    if isinstance(res, dict):
        if "message" in res:
            res["message"] = res["message"].replace("Active spec", "Active spec")
        if "spec_id" in res:
            res["domain_id"] = res["spec_id"]
        if "spec_name" in res:
            res["domain_name"] = res["spec_name"]
        if "spec_summary" in res:
            res["domain_summary"] = res["spec_summary"]
        if "key_messages_count" in res:
            res["assertion_count"] = res["key_messages_count"]
    return res


@mcp.tool()
def get_spec(
    domain_id: Optional[str] = None,
    domain_name: Optional[str] = None,
    include_unapproved: bool = False,
) -> dict:
    """Retrieve full content of a spec for research.

    By default only returns entries with status APPROVED or LOCKED.
    Use include_unapproved=True to include DRAFT and IN_REVIEW entries.
    OUTDATED entries are always excluded.

    Use this tool to understand the positioning, target audience, and approved assertions.
    
    CRITICAL: Do NOT use the data returned here to manually write a one-pager or 
    artifact for the user. Instead, use 'generate_artifact' or 'build_ui_artifact'.

    Args:
        domain_id: UUID of the spec.
        domain_name: Name of the spec (alternative to domain_id).
        include_unapproved: If True, also include DRAFT and IN_REVIEW entries.
    """
    res = grounding_tools.get_spec(domain_id, domain_name, ["all"], include_unapproved=include_unapproved)
    # Align terminology in output keys
    if isinstance(res, dict):
        if "id" in res:
            res["domain_id"] = res["id"]
            res["spec_id"] = res["id"]
        if "name" in res:
            res["domain_name"] = res["name"]
            res["spec_name"] = res["name"]
        if "assertions" in res:
            res["assertions"] = res["assertions"]
    return res


@mcp.tool()
def list_specs(query: Optional[str] = None, workspace_id: Optional[str] = None, department: Optional[str] = None) -> dict:
    """List all available specs with their IDs and summaries.

    Call this FIRST whenever the user mentions a brand, product, company, or policy
    domain — before calling any generate or search tool. Use the returned
    domain_id (UUID) for all subsequent tool calls.

    IMPORTANT: The 'summary' in the response is a 2–3 sentence overview ONLY.
    It does NOT contain the actual approved assertions or proof points.
    After identifying the domain_id:
    - To GENERATE an output → call generate_artifact(skill_id, domain_id)
    - To READ full grounding content → call get_spec(domain_id)
    Never write content yourself using only this tool's output.

    Args:
        query: Optional text search across spec names and summaries.
        workspace_id: Filter to a specific workspace (optional).
        department: Filter to a specific department (optional).
    """
    res = grounding_tools.list_specs(query, workspace_id)
    # Align terminology in output
    if isinstance(res, dict) and "specs" in res:
        res["domains"] = [
            {
                "domain_id": h.get("id"),
                "id": h.get("id"),
                "name": h.get("name"),
                "summary": h.get("summary"),
                "department": h.get("department", "General"),
            }
            for h in res["specs"]
            if not department or h.get("department", "General").lower() == department.lower()
        ]
    return res


@mcp.tool()
def compare_specs(domain_ids: list[str], include_unapproved: bool = False) -> dict:
    """Compare two or more specs side by side.

    By default only includes entries with status APPROVED or LOCKED.
    Use include_unapproved=True to include DRAFT and IN_REVIEW entries.

    Useful for comparing different departments or product lines.

    Args:
        domain_ids: UUIDs of the specs to compare.
        include_unapproved: If True, also include DRAFT and IN_REVIEW entries.
    """
    return grounding_tools.compare_specs(domain_ids, include_unapproved=include_unapproved)


@mcp.tool()
def get_grounding_context() -> dict:
    """Get the current grounding context for this session.

    Returns which spec is active, which audiences are in scope, and which
    chunks have been used so far.
    """
    return grounding_tools.get_grounding_context().model_dump()


@mcp.tool()
def get_assertion_history(entry_id: str) -> dict:
    """Get the full approval/status-change audit trail for a specific assertion.

    Returns the complete history of status changes, reviews, and approvals
    for the given entry, ordered newest-first. Mirrors the review-trail data shape.

    Args:
        entry_id: The UUID of the assertion.

    Returns:
        dict with entry_id, current_status, trail (list of review log entries), and count.
    """
    return grounding_tools.get_assertion_history(entry_id)


def _resolve_spec(store, spec_id: Optional[str], spec_name: Optional[str] = None):
    """Resolve a message spec by ID (UUID) or name, with fallback."""
    from uuid import UUID as _UUID
    spec = None
    if spec_id:
        try:
            spec = store.get_spec(_UUID(spec_id))
        except (ValueError, AttributeError):
            pass
    if spec is None and spec_name:
        spec = store.get_spec_by_name(spec_name)
    if spec is None and spec_id:
        spec = store.get_spec_by_name(spec_id)
    return spec


def generate_one_pager_data(spec_id: str) -> dict:
    """Internal helper to get structured data for a one-pager."""
    store = get_store()
    spec = _resolve_spec(store, spec_id)
    if not spec:
        return {"error": f"Spec not found."}

    messages = store.get_key_messages(spec.id)
    audiences = store.get_audiences(spec.id)

    grouped = {}
    for m in messages:
        key = str(m.assertion_type)
        grouped.setdefault(key, []).append(m.content)

    return {
        "spec_name": spec.name,
        "tagline": spec.tagline,
        "positioning": spec.positioning,
        "differentiation": spec.differentiation,
        "audience": spec.audience,
        "assertions": grouped,
        "audiences": [{"name": p.name, "description": p.description, "qa_pairs": p.qa_pairs} for p in audiences],
        "message_count": len(messages),
    }


@mcp.tool()
def generate_artifact(
    skill_id: str,
    domain_id: Optional[str] = None,
    domain_name: Optional[str] = None,
    custom_context: Optional[dict] = None,
    spec_id: Optional[str] = None,
    spec_name: Optional[str] = None,
    include_unapproved: bool = False,
) -> str:
    """Generate an output draft from a spec using a derived template skill.

    CALL THIS TOOL IMMEDIATELY — do not explain, do not show code, do not ask for confirmation —
    whenever the user says anything like: "generate", "create", "write", "build", "make", "draft",
    "give me", "show me", "produce", or "put together" followed by any of:
    one-pager, datasheet, battlecard, email, post, release, FAQ, script, or other document.

    You can pass domain_name instead of domain_id — no prior lookup needed.
    NEVER write the content yourself. ALWAYS call this tool instead.

    The tool runs the AI generator and returns the full content PLUS a visual link.

    Args:
        skill_id: Content type — one of: one_pager, linkedin_post, email_template,
                  battlecard, press_release, blog_post, faq_document, talk_track,
                  qa_pair_handler, event_brief, executive_summary, partner_brief.
        domain_id: UUID of the spec (preferred over domain_name).
        domain_name: Exact name of the spec (used if domain_id not available).
        custom_context: Extra context dict, e.g. {"competitor": "Salesforce"} for battlecard
                        or {"stage": "decision"} for email_template.
        spec_id: UUID of the spec (legacy alias for domain_id).
        spec_name: Exact name of the spec (legacy alias for domain_name).
        include_unapproved: If True, allow draft and in_review entries to ground the artifact.
    """
    from src.pipeline.generator import ArtifactGenerator
    from src.pipeline.skills import SkillManager
    from src.grounding.session import get_session

    store = get_store()

    actual_id = domain_id or spec_id
    actual_name = domain_name or spec_name

    spec = None
    if actual_id:
        try:
            from uuid import UUID as _UUID
            spec = store.get_spec(_UUID(actual_id))
        except (ValueError, AttributeError):
            spec = None
    if spec is None and actual_name:
        spec = store.get_spec_by_name(actual_name)
    if spec is None and actual_id and not actual_name:
        spec = store.get_spec_by_name(actual_id)
    if spec is None:
        all_specs = store.list_specs()
        names = ", ".join(h.name for h in all_specs)
        return f"Domain not found. Call list_specs to see valid options. Available: {names}"

    skills = SkillManager(skills_dir="data/skills")

    # Check required context inputs before running the generator
    from src.pipeline.skills import SKILL_CONTEXT_INPUTS
    required_inputs = SKILL_CONTEXT_INPUTS.get(skill_id, [])
    provided = custom_context or {}
    if include_unapproved:
        provided["include_drafts"] = True
    missing = [inp for inp in required_inputs if inp.get("required") and inp["key"] not in provided]
    if missing:
        labels = " and ".join(f'"{inp["label"]}"' for inp in missing)
        example = {inp["key"]: inp.get("placeholder", f"<{inp['label']}>") for inp in missing}
        return (
            f'To generate a {skill_id.replace("_", " ")}, I need {labels}. '
            f'Please provide it via `custom_context`, e.g. `{{"custom_context": {example}}}`.'
        )

    generator = ArtifactGenerator(store, skills)
    artifact = generator.generate(skill_id, str(spec.id), provided)

    try:
        from src.pipeline.alignment import AlignmentEngine
        score = AlignmentEngine(store).score(spec.id, artifact.raw_content).overall_score
    except Exception:
        score = None

    try:
        saved = store.save_artifact(
            spec_id=spec.id,
            skill_id=skill_id,
            spec_name=artifact.spec_name,
            sections=artifact.sections,
            raw_content=artifact.raw_content,
            alignment_score=score,
        )
        artifact_history_id = saved["id"]
    except Exception:
        artifact_history_id = None

    # Record in grounding session so get_grounding_context reflects this
    session = get_session()
    workspace_id = store.get_spec_workspace_id(spec.id) or "default"
    session.set_active_spec(
        spec_id=spec.id,
        spec_name=spec.name,
        spec_summary=spec.summary or "",
        audiences=[],
        workspace_id=workspace_id,
    )

    base_url = os.environ.get("MSGSTACK_BASE_URL", "http://localhost:8001")
    
    content = artifact.raw_content
    if getattr(artifact, "used_drafts_fallback", False):
        content = (
            "> [!WARNING]\n"
            "> Grounded in draft (unapproved) assertions because no approved entries exist for this domain.\n\n"
            + content
        )
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
            url = f"{base_url}/artifact/{artifact_type}/{spec.id}"
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
    domain_id: Optional[str] = None,
    domain_name: Optional[str] = None,
    stage: Optional[str] = None,
    channels: Optional[list[str]] = None,
    spec_id: Optional[str] = None,
    spec_name: Optional[str] = None,
) -> str:
    """Return a visual HTML page URL for a spec — does NOT run the AI generator.

    Use this ONLY when the user asks for a "link", "page", "visual", or "web view"
    of a domain that already exists — NOT to generate new content.

    To actually generate content (one-pager, email, battlecard, etc.), use
    generate_artifact instead.

    Args:
        artifact_type: one_pager | social_posts | email_template | battlecard
        domain_id: UUID of the spec (preferred).
        domain_name: Exact name of the spec.
        stage: For email_template only: awareness | consideration | decision
        channels: For social_posts only: e.g. ["linkedin"]
        spec_id: UUID of the spec (legacy alias).
        spec_name: Exact name of the spec (legacy alias).
    """
    store = get_store()
    actual_id = domain_id or spec_id
    actual_name = domain_name or spec_name
    spec = _resolve_spec(store, actual_id, actual_name)
    if not spec:
        all_specs = store.list_specs()
        return "Spec domain not found. Available: " + ", ".join(h.name for h in all_specs)

    valid_types = ["one_pager", "social_posts", "email_template", "battlecard"]
    if artifact_type not in valid_types:
        return f"Unknown artifact_type. Choose: {', '.join(valid_types)}"

    base_url = os.environ.get("MSGSTACK_BASE_URL", "http://localhost:8001")
    params = ""
    if artifact_type == "email_template" and stage:
        params = f"?stage={stage}"
    elif artifact_type == "social_posts" and channels:
        params = f"?channels={','.join(channels)}"

    url = f"{base_url}/artifact/{artifact_type}/{spec.id}{params}"
    return f"Open the {artifact_type.replace('_', ' ')} for **{spec.name}**: {url}"


@mcp.tool()
def list_skills() -> dict:
    """List all available derived output templates (skills).

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
        {"name": "search_assertions", "description": "Search approved specs for grounding content (headlines, proof points, etc)."},
        {"name": "list_specs", "description": "List all available specs/categories."},
        {"name": "get_spec", "description": "Retrieve full spec content for deep research (positioning, audiences)."},
        {"name": "list_skills", "description": "List all 12+ types of output templates you can generate (Email, PR, Blog, etc)."},
        {"name": "generate_artifact", "description": "MANDATORY: Generate a full document draft grounded in approved assertions."},
        {"name": "build_ui_artifact", "description": "Get a visual HTML link for a specific spec artifact."},
        {"name": "set_active_spec", "description": "Focus the session on a specific spec."},
        {"name": "check_spec_completeness", "description": "Audit a spec for missing critical entries/metadata."},
        {"name": "get_schema", "description": "See the requirements for a complete spec."},
        {"name": "export_to_penpot", "description": "Export a MsgStack artifact to Penpot design file and return the edit link."},
        {"name": "set_penpot_project", "description": "Link a Penpot project to a MsgStack workspace for design sync."},
        {"name": "get_assertion_history", "description": "Get the full approval/status-change audit trail for a specific assertion."},
    ]
    return {"tools": tool_defs}


@mcp.tool()
def export_to_penpot(
    artifact_id: str,
    workspace_id: str,
    domain_id: Optional[str] = None,
    spec_id: Optional[str] = None,
) -> dict:
    """Export a MsgStack artifact to Penpot and return the edit link.

    Creates a fully designed Penpot file with frames, text layers,
    brand colors, and proper layout matching the artifact's design spec.

    Args:
        artifact_id: The artifact ID to export.
        workspace_id: The workspace ID (to find the linked Penpot project).
        domain_id: the spec ID (to get brand tokens and approved entries).
        spec_id: the spec ID (legacy alias for domain_id).

    Returns:
        dict with file_id, edit_url, and creation status.
    """
    actual_id = domain_id or spec_id
    if not actual_id:
        return {"error": "domain_id or spec_id is required"}
    return grounding_tools.export_to_penpot(artifact_id, workspace_id, actual_id)


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

    Clears the active domain, recent searches, and used chunks.
    Use when starting a new topic or switching specs.
    """
    reset_session()
    return {"message": "Session reset. No active spec."}


@mcp.tool()
def get_schema() -> dict:
    """Return the specification for a complete MsgStack spec.

    Use this to understand what a fully-populated spec should contain:
    required fields, section types, entry counts, audience structure, and
    channel variants. Also returns a completeness checklist.
    """
    from src.models import COMPLETE_SCHEMA_SPEC
    return COMPLETE_SCHEMA_SPEC


@mcp.tool()
def check_spec_completeness(domain_id: Optional[str] = None, domain_name: Optional[str] = None) -> dict:
    """Check how complete a spec is against the specification.

    Returns a completeness report with what's present, what's missing, and a score.

    Args:
        domain_id: UUID of the spec.
        domain_name: Name of the spec (alternative to domain_id).
    """
    from src.models import COMPLETE_SCHEMA_SPEC, AssertionType

    store = get_store()
    spec = _resolve_spec(store, domain_id, domain_name)
    if not spec:
        return {"error": "Domain not found. Use list_specs to find valid IDs."}

    messages = store.get_key_messages(spec.id)
    audiences = store.get_audiences(spec.id)

    by_section = {}
    for m in messages:
        key = str(m.assertion_type)
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

    check("Positioning field filled (50+ chars)", len(spec.positioning or "") >= 50)
    check("Tagline present and under 60 chars", bool(spec.tagline) and len(spec.tagline) < 60)
    check("Differentiation is specific (30+ chars)", len(spec.differentiation or "") >= 30)
    check("Audience defined", bool(spec.audience))
    check("Brand personality defined", bool(spec.brand_personality))

    required_min = {"headline": 3, "subhead": 3, "benefit": 3, "proof_point": 3, "qa_pair": 3, "social_proof": 3, "positioning": 1}
    for section, min_count in required_min.items():
        msgs = by_section.get(section, [])
        check(f"{section}: {min_count}+ entries (has {len(msgs)})", len(msgs) >= min_count)

    check("2+ audiences defined", len(audiences) >= 2)
    for p in audiences[:3]:
        check(f"Audience '{p.name}': Q&A pairs defined", bool(p.qa_pairs))
        check(f"Audience '{p.name}': qa_pairs defined", bool(p.qa_pairs))

    msgs_with_linkedin = sum(1 for m in messages if (m.variants or {}).get("linkedin"))
    msgs_with_email = sum(1 for m in messages if (m.variants or {}).get("email"))
    check(f"LinkedIn variants on 5+ entries (has {msgs_with_linkedin})", msgs_with_linkedin >= 5)
    check(f"Email variants on 5+ entries (has {msgs_with_email})", msgs_with_email >= 5)

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
                recommendations.append("Define the primary target audience in the domain metadata.")
            elif "Brand personality" in label:
                recommendations.append("Add brand personality traits (e.g., bold, empathetic, technical).")
            elif "audiences" in label.lower():
                recommendations.append("Define at least 2 distinct buyer audiences with pain points and triggers.")
            elif "LinkedIn" in label:
                recommendations.append("Add LinkedIn channel variants to at least 5 entries.")
            elif "Email" in label:
                recommendations.append("Add email channel variants to at least 5 entries.")
            else:
                # section-level check: extract section name
                section = label.split(":")[0].strip()
                recommendations.append(f"Add more {section} entries (minimum required not met).")

    return {
        "domain_name": spec.name,
        "spec_name": spec.name,
        "score": score,
        "passed": passed,
        "total": total,
        "checks": checks,
        "missing": [c["check"] for c in checks if not c["passed"]],
        "recommendations": recommendations,
        "assertion_count": len(messages),
        "message_count": len(messages),
        "audience_count": len(audiences),
        "sections_covered": list(by_section.keys()),
    }


@mcp.tool()
def score_alignment_report(text: str, domain_id: str) -> str:
    """
    Audit and score draft text against the approved spec.
    Returns a formatted markdown alignment report indicating hard and soft conflicts.

    Use `score_alignment` instead when you want structured JSON. These two run
    different engines and are a dedup candidate — see STRATEGY_V2.md.
    """
    from uuid import UUID
    from src.store import get_store
    from src.pipeline.alignment import score_alignment, export_report_to_markdown

    store = get_store()
    try:
        uid = UUID(domain_id)
    except ValueError:
        return "Error: Invalid domain_id UUID format."

    domain = store.get_spec(uid)
    if not domain:
        return f"Error: Spec domain with ID '{domain_id}' not found."

    try:
        report = score_alignment(text, uid, store)
        markdown_report = export_report_to_markdown(report)
        return markdown_report
    except Exception as e:
        return f"Error executing alignment score audit: {e}"


@mcp.tool()
def score_alignment(
    domain_id: str,
    content: str,
) -> dict:
    """Score arbitrary content against the spec.

    This tool evaluates a piece of content (like a drafted blog post, email, 
    or any external text) against the approved entries in the specified spec.
    It returns a JSON report containing an overall alignment score (0-100), section-by-section
    breakdown, any contradictions found, and missing assertions.

    Args:
        domain_id: UUID of the spec to score against.
        content: The raw text content to evaluate.
    """
    from src.pipeline.alignment import AlignmentEngine
    from uuid import UUID
    
    store = get_store()
    try:
        spec_uuid = UUID(domain_id)
    except Exception:
        return {"error": "Invalid domain_id"}

    engine = AlignmentEngine(store)
    try:
        report = engine.score(spec_uuid, content)
        res = report.model_dump()
        if "spec_id" in res:
            res["domain_id"] = res["spec_id"]
        return res
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_graph_connections(
    domain_id: Optional[str] = None,
    audience: Optional[str] = None,
    channel: Optional[str] = None,
    spec_id: Optional[str] = None,
) -> dict:
    """Retrieve verbatim approved assertions via deterministic graph traversal.

    Unlike search_assertions (which uses vector approximation), this tool queries
    the knowledge graph directly — returning exactly the content associated with
    a domain, audience, or channel via typed relationships. Use this when you need:
    - An exact approved tagline or headline (not the nearest neighbor)
    - All entries that apply to a specific audience
    - All entries approved for a specific channel

    Args:
        domain_id: UUID of the spec to query.
        audience: Optional audience name to filter by ADDRESSES relationship.
        channel: Optional channel to filter by APPLIES_TO relationship.
        spec_id: UUID of the spec to query (legacy alias).

    Returns:
        List of content chunks retrieved via graph traversal (confidence=1.0).
    """
    actual_id = domain_id or spec_id
    if not actual_id:
        return {"error": "domain_id or spec_id is required"}

    from src.grounding.graph import get_graph_engine
    engine = get_graph_engine()
    chunks = engine.get_connections(actual_id, audience=audience, channel=channel)
    return {
        "retrieval_mode": "graph",
        "domain_id": actual_id,
        "spec_id": actual_id,
        "audience_filter": audience,
        "channel_filter": channel,
        "count": len(chunks),
        "chunks": [{"content": c.get("content", ""), "assertion_type": c.get("assertion_type", ""),
                    "priority": c.get("priority", 3)} for c in chunks],
    }


@mcp.tool()
def list_channels() -> dict:
    """List all available channels (including user-defined custom channels).

    Returns the full channel registry — both the default channels (email, linkedin,
    twitter, etc.) and any custom channels added by the team. Use channel IDs as
    the 'channels' filter in search_assertions or get_graph_connections.
    """
    store = get_store()
    return {"channels": store.get_channels()}


@mcp.tool()
def list_departments() -> dict:
    """List all departments, their default primary grounding types, and domain counts.

    Use this tool to see the departmental organization of your specs.
    """
    store = get_store()
    domains = store.list_specs()
    depts = store.list_departments()
    
    counts = {}
    for d in domains:
        counts[d.department] = counts.get(d.department, 0) + 1
        
    result = []
    for dept in depts:
        name = dept["name"]
        result.append({
            "department": name,
            "primary_schema_type": dept["primary_schema_type"],
            "description": dept["description"],
            "domain_count": counts.get(name, 0),
        })
    return {"departments": result}


@mcp.tool()
def traverse_graph(
    assertion_ids: list[str],
    hops: int = 2,
    rel_types: Optional[list[str]] = None,
    limit: int = 25,
) -> dict:
    """Walk the knowledge graph outward from one or more assertions.

    Follows typed relationships — DEPENDS_ON, INFORMS, SUPERSEDES, CONTRADICTS,
    IMPLEMENTS, MENTIONS — in both directions, and crosses spec boundaries:
    an assertion in a different spec that references the same entity, or that
    a dependency edge points at, is reachable here but not via search.

    Use this to answer "what else is affected by this?" or "what does this
    depend on?" rather than "what is similar to this?".

    Args:
        assertion_ids: UUIDs of the assertions to start from.
        hops: Maximum path length. 2 is usually right — 1 finds only direct
            neighbours, 3+ tends to reach weakly related material.
        rel_types: Restrict to these relationships. All types if omitted.
        limit: Maximum assertions to return.
    """
    from src.grounding.graph import get_graph_engine
    found = get_graph_engine().expand(
        assertion_ids, hops=hops, rel_types=rel_types, limit=limit
    )
    return {
        "seeds": assertion_ids,
        "hops": hops,
        "results": [{
            "assertion_id": f.get("id"),
            "content": f.get("content"),
            "assertion_type": f.get("assertion_type"),
            "status": f.get("status"),
            "weight": f.get("graph_weight"),
            "hops": f.get("hops"),
            "path": f.get("graph_path"),
        } for f in found],
        "count": len(found),
    }


@mcp.tool()
def get_impact(node_id: str, node_type: str = "assertion") -> dict:
    """Show everything that goes stale if this node changes.

    Walks inbound DEPENDS_ON and INFORMS edges transitively. Call this before
    editing an assertion to see the blast radius — the same traversal that runs
    automatically on write and marks dependents outdated.
    """
    store = get_store()
    direct = store.get_dependents(node_type, node_id)
    return {
        "node": {"type": node_type, "id": node_id},
        "direct_dependents": direct,
        "direct_count": len(direct),
    }


@mcp.tool()
def link_assertions(
    src_assertion_id: str,
    dst_assertion_id: str,
    rel_type: str = "DEPENDS_ON",
    provenance: str = "",
) -> dict:
    """Create a typed relationship between two assertions.

    DEPENDS_ON and INFORMS are propagating: when the destination changes, the
    source is automatically marked outdated. SUPERSEDES, CONTRADICTS,
    IMPLEMENTS and OWNS are navigational — they shape traversal without
    cascading staleness.

    Args:
        src_assertion_id: The dependent / referring assertion.
        dst_assertion_id: The assertion depended on / referred to.
        rel_type: One of DEPENDS_ON, INFORMS, SUPERSEDES, CONTRADICTS,
            IMPLEMENTS, OWNS, MENTIONS.
        provenance: Free text recording why this link exists.
    """
    from src.models import RelType
    store = get_store()
    try:
        rel = RelType(rel_type).value
    except ValueError:
        return {"error": f"Unknown rel_type {rel_type!r}. Valid: {[r.value for r in RelType]}"}
    try:
        edge_id = store.add_edge(
            "assertion", src_assertion_id, "assertion", dst_assertion_id,
            rel, provenance=provenance, created_by="mcp",
        )
    except ValueError as e:
        return {"error": str(e)}
    return {"edge_id": edge_id, "rel_type": rel,
            "src": src_assertion_id, "dst": dst_assertion_id}


# ── MCP Prompts ──────────────────────────────────────────────────────────────
# Clients that support prompts/list (OpenWebUI, Claude Desktop, etc.) will
# discover these and can inject them as system messages automatically.

@mcp.prompt()
def system_instructions() -> str:
    """Complete operating guide for MsgStack tools. Inject at conversation start."""
    return """You are connected to MsgStack, the organization's authoritative spec graph grounding layer.

## Tool Selection Rules

**GENERATE content** — call `generate_artifact` immediately. NEVER write the content yourself.
Triggers: "build", "make", "create", "generate", "write", "draft", "give me", "show me",
"put together", "can you make" + any of: one-pager, datasheet, battlecard, email, post,
release, FAQ, script, or other document.

**SEARCH the spec graph** — call `search_assertions` when:
- User asks what approved assertions exist for a topic, audience, or channel
- You need grounding before writing any copy yourself
- User asks for headlines, proof points, qa_pairs, or talking points

**LIST / BROWSE** — use `list_specs` when the user hasn't specified a domain,
and `list_skills` when they haven't specified an artifact/output type.

**RESEARCH a domain** — call `get_spec` when the user wants to understand
a domain's positioning, audiences, or approved assertions.

## Output Rules

- When `generate_artifact` returns content, paste it **verbatim and in full**. Do not
  summarize, paraphrase, or describe it. The user wants the actual document.
- When `search_assertions` returns results, quote the returned assertions directly.
- Always include visual links when returned by the tool.

## Standard Generation Workflow

1. If no domain is specified → call `list_specs` and ask the user to pick one.
2. If no artifact type is specified → call `list_skills` and ask which they want.
3. Call `generate_artifact` with `skill_id` + `spec_id` (+ `custom_context` if needed).
4. Paste the full returned content. Done.

## Required custom_context per skill

- battlecard: `custom_context={"competitor": "<name>"}` — REQUIRED
- blog_post: `custom_context={"topic": "<topic>"}` — REQUIRED
- press_release: `custom_context={"announcement": "<summary>"}` — REQUIRED
- event_brief: `custom_context={"event_name": "<name>"}` — REQUIRED
- email_template: `custom_context={"stage": "awareness|consideration|decision"}` — optional

## When to use get_graph_connections vs search_assertions

- Use `get_graph_connections` when you need **exact, verbatim approved content** — locked taglines,
  specific proof points, or all entries for a audience. Confidence is always 1.0 (no approximation).
- Use `search_assertions` for **exploratory or semantic queries** where you want the closest match
  to a natural language request. Use `retrieval_mode="graph"` as a shortcut for the same effect.

## Content Tier Contract

Spec entries carry a `content_tier` that governs how you may use them:

- **tier_1_locked** — Sacrosanct. Reproduce the entry text VERBATIM wherever its content is used.
  Never paraphrase, shorten, restyle, or approximate a Tier 1 entry. If it doesn't fit, use a
  different entry — do not alter it.
- **tier_2_structured** — Substance-locked. Keep the meaning, claims, and positioning intact;
  you may adapt phrasing to fit the output format.
- **tier_3_grounded** (or untagged) — Flexible. Stay consistent with the spec graph's direction and
  tone; phrasing and structure are yours.
"""


@mcp.prompt()
def quick_start() -> str:
    """One-paragraph quick-start guide shown to users new to MsgStack."""
    return """MsgStack gives you AI-generated marketing and technical artifacts grounded in your approved assertions.

Call `list_specs` to see available specs, then use the returned spec_id for all other tools.

**To generate a document**, just say what you want and which domain/product, e.g.:
- "Write a one-pager for [domain name]"
- "Build a battlecard for [domain name] vs [competitor]"
- "Draft a post for [domain name]"

Available artifact types: one-pager, battlecard, email template, post, blog post,
press release, FAQ, talk track, qa_pair handler, executive summary, partner brief, event brief.
"""


def main():
    mcp.run()


if __name__ == "__main__":
    main()