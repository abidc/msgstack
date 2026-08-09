"""Penpot integration for design token sync and artifact export."""

from typing import Optional
from uuid import UUID

from src.models import Spec, Assertion, Audience, AssertionType
from src.store import Store, get_store


def _extract_brand_colors(spec: Spec) -> dict[str, str]:
    """Extract brand colors from spec data."""
    colors = {
        "primary": "#1a73e8",
        "secondary": "#34a853",
        "accent": "#fbbc04",
        "text": "#202124",
        "background": "#ffffff",
    }
    personality = (spec.positioning or "").lower()
    if "bold" in personality or "strong" in personality:
        colors["primary"] = "#d93025"
    elif "calm" in personality or "trust" in personality:
        colors["primary"] = "#1a73e8"
    elif "creative" in personality or "innovative" in personality:
        colors["primary"] = "#9334e6"
    return colors


def _map_personality_to_font(personality: str) -> str:
    """Map brand personality to appropriate font family."""
    personality = (personality or "").lower()
    if "modern" in personality or "clean" in personality:
        return "Inter"
    elif "traditional" in personality or "classic" in personality:
        return "Georgia"
    elif "tech" in personality or "startup" in personality:
        return "Roboto"
    elif "friendly" in personality or "approachable" in personality:
        return "Nunito"
    return "Work Sans"


def _call_penpot_tool(tool_name: str, **kwargs):
    """Call a Penpot MCP tool if available in the environment."""
    # The Penpot MCP tools are available as registered MCP tools
    # We try to import and call them directly
    tool_mapping = {
        "penpot_create_project": "penpot_create_project",
        "penpot_create_file": "penpot_create_file",
        "penpot_get_file": "penpot_get_file",
        "penpot_list_pages": "penpot_list_pages",
        "penpot_get_page_shapes": "penpot_get_page_shapes",
        "penpot_create_frame": "penpot_create_frame",
        "penpot_create_text": "penpot_create_text",
        "penpot_create_rectangle": "penpot_create_rectangle",
        "penpot_create_font_variant": "penpot_create_font_variant",
    }
    func_name = tool_mapping.get(tool_name, tool_name)

    # Try to call the function directly - it may be available in the namespace
    # The MCP tools are registered functions that can be called
    try:
        import builtins
        if hasattr(builtins, func_name):
            func = getattr(builtins, func_name)
            return func(**kwargs)
    except Exception:
        pass

    # Return a structured response indicating what tool to call
    return {"_tool_call": func_name, "_kwargs": kwargs}


def get_or_create_penpot_project(workspace_id: str, workspace_name: str, team_id: str = "default") -> str | None:
    """Get existing Penpot project or return None if needs creation."""
    store = get_store()
    existing = store.get_penpot_project(workspace_id)
    return existing


def sync_brand_tokens_to_penpot(workspace_id: str, spec: Spec) -> dict:
    """Sync MsgStack brand tokens to Penpot design tokens."""
    store = get_store()
    project_id = store.get_penpot_project(workspace_id)

    results = {
        "workspace_id": workspace_id,
        "spec_name": spec.name,
        "brand_colors": _extract_brand_colors(spec),
        "font_family": _map_personality_to_font(spec.positioning),
        "project_id": project_id,
        "actions": [],
    }

    if not project_id:
        # Return action to create project
        results["actions"].append({
            "tool": "penpot_create_project",
            "params": {
                "teamId": "default",
                "name": f"MsgStack - {spec.name}",
            },
        })
    else:
        # Create file for brand
        results["actions"].append({
            "tool": "penpot_create_file",
            "params": {
                "projectId": project_id,
                "name": f"Brand: {spec.name}",
            },
        })

    return results


def export_artifact_to_penpot(artifact_id: str, workspace_id: str, spec: Spec) -> dict:
    """Export a MsgStack artifact to a Penpot file.

    Returns a dict with the file details and instructions for creating
    the Penpot design via MCP tool calls.
    """
    store = get_store()
    project_id = store.get_penpot_project(workspace_id)

    results = {
        "artifact_id": artifact_id,
        "workspace_id": workspace_id,
        "spec_name": spec.name,
        "project_id": project_id,
        "edit_url": None,
        "file_id": None,
        "design_spec": None,
        "errors": [],
    }

    if not project_id:
        results["errors"].append("No Penpot project linked to workspace.")
        results["hint"] = {
            "action": "create_project",
            "tool": "penpot_create_project",
            "params": {
                "teamId": "default",
                "name": f"MsgStack - {spec.name}",
            },
        }
        return results

    # Build design specification
    brand_colors = _extract_brand_colors(spec)
    font_family = _map_personality_to_font(spec.positioning)

    design_spec = {
        "file": {
            "tool": "penpot_create_file",
            "params": {
                "projectId": project_id,
                "name": f"Artifact: {spec.name}",
            },
        },
        "steps": [],
    }

    # After file creation, these steps should be executed
    # (fileId and pageId will be filled in after file creation)
    steps = []

    # Create main frame
    steps.append({
        "tool": "penpot_create_frame",
        "params": {
            "name": f"Artifact - {spec.name}",
            "width": 1200,
            "height": 1600,
            "fillColor": "#ffffff",
        },
    })

    y_offset = 40

    # Add headline
    if spec.tagline:
        steps.append({
            "tool": "penpot_create_text",
            "params": {
                "name": "Headline",
                "text": spec.tagline,
                "x": 40,
                "y": y_offset,
                "fontSize": 32,
                "fontWeight": "bold",
                "fillColor": brand_colors.get("primary", "#000000"),
                "fontFamily": font_family,
            },
        })
        y_offset += 60

    # Add positioning
    if spec.positioning:
        steps.append({
            "tool": "penpot_create_text",
            "params": {
                "name": "Positioning",
                "text": spec.positioning[:200],
                "x": 40,
                "y": y_offset,
                "fontSize": 16,
                "fillColor": brand_colors.get("text", "#202124"),
                "fontFamily": font_family,
            },
        })
        y_offset += 100

    # Add key messages header
    steps.append({
        "tool": "penpot_create_text",
        "params": {
            "name": "Key Messages Header",
            "text": "Key Messages",
            "x": 40,
            "y": y_offset,
            "fontSize": 24,
            "fontWeight": "bold",
            "fillColor": brand_colors.get("secondary", "#34a853"),
            "fontFamily": font_family,
        },
    })
    y_offset += 50

    # Add key messages
    messages = store.get_key_messages(spec.id)
    for i, msg in enumerate(messages[:10]):
        steps.append({
            "tool": "penpot_create_text",
            "params": {
                "name": f"Message {i+1}: {msg.assertion_type}",
                "text": f"[{msg.assertion_type}] {msg.content[:150]}",
                "x": 40,
                "y": y_offset,
                "fontSize": 14,
                "fillColor": brand_colors.get("text", "#202124"),
                "fontFamily": font_family,
            },
        })
        y_offset += 30

    design_spec["steps"] = steps
    results["design_spec"] = design_spec
    results["edit_url"] = f"https://design.penpot.app/work/#/project/{project_id}"

    return results


def pull_from_penpot(penpot_file_id: str, workspace_id: str) -> dict:
    """Extract design decisions from a Penpot file."""
    return {
        "file_id": penpot_file_id,
        "workspace_id": workspace_id,
        "actions": [
            {
                "tool": "penpot_get_file",
                "params": {"fileId": penpot_file_id},
            },
        ],
    }


def handle_penpot_webhook(webhook_data: dict) -> dict:
    """Handle incoming Penpot webhook for design changes."""
    event_type = webhook_data.get("type", "")
    file_id = webhook_data.get("file-id") or webhook_data.get("file_id")

    if not file_id:
        return {"error": "No file ID in webhook data"}

    return {
        "event_type": event_type,
        "file_id": file_id,
        "action": "sync-attempted" if event_type in ("file-update", "file-change", "update") else "ignored",
    }
