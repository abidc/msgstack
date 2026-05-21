"""Pydantic validation for visual design specifications (Schema v2)."""

from pydantic import BaseModel, Field
from typing import Optional
import json
import logging

log = logging.getLogger(__name__)

from src.design.schema_v2 import DesignSpec, Zone, PageSpec, PagePreset, ZoneType

def validate_and_fill_design_spec(
    raw_json: str,
    template_zones: list[Zone],
    house_data: dict,
) -> DesignSpec:
    """
    Validate LLM output against DesignSpec (Schema v2).
    - Parse JSON
    - Validate with Pydantic
    - Inject default template zones if missing
    - Apply constraints and token truncation
    """
    try:
        if isinstance(raw_json, str):
            clean_json = raw_json.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            parsed = json.loads(clean_json.strip())
        else:
            parsed = raw_json
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in design spec: {e}")

    # Ensure zones list exists
    zones_out = parsed.get("zones", [])
    if not isinstance(zones_out, list):
        zones_out = []

    # Map zones by ID
    existing_zones = {}
    for z in zones_out:
        if isinstance(z, dict) and "id" in z:
            existing_zones[z["id"]] = z

    # If any required zone from template is missing, inject it
    for tz in template_zones:
        if tz.id not in existing_zones:
            # Construct default Zone dict
            zone_dict = tz.model_dump()
            # Try to resolve placeholders in default content
            zone_dict["text_content"] = _resolve_placeholder(tz.text_content, house_data)
            zone_dict["list_items"] = [_resolve_placeholder(item, house_data) for item in tz.list_items]
            zones_out.append(zone_dict)
            existing_zones[tz.id] = zone_dict
        else:
            # Zone exists, apply constraint truncation
            z_dict = existing_zones[tz.id]
            if "text_content" in z_dict and isinstance(z_dict["text_content"], str):
                z_dict["text_content"] = z_dict["text_content"][:1000]
            if "list_items" in z_dict and isinstance(z_dict["list_items"], list):
                z_dict["list_items"] = [str(item)[:500] for item in z_dict["list_items"]]

    parsed["zones"] = zones_out

    # Ensure page_spec exists
    if "page_spec" not in parsed:
        parsed["page_spec"] = PageSpec.from_preset(PagePreset.LETTER).model_dump()

    # Validate and return
    return DesignSpec(**parsed)

def _resolve_placeholder(text: str, house_data: dict) -> str:
    """Helper to resolve placeholders like {positioning} from house_data."""
    if not text:
        return text
    res = text
    placeholders = {
        "{house_name}": house_data.get("house_name") or house_data.get("name") or "",
        "{tagline}": house_data.get("tagline") or "",
        "{positioning}": house_data.get("positioning") or "",
        "{differentiation}": house_data.get("differentiation") or "",
        "{proof_point}": _get_first_proof_point(house_data),
        "{competitor}": house_data.get("competitor") or "Competitor",
    }
    
    # Handlers for list item placeholders
    benefits = house_data.get("benefits", [])
    if not benefits:
        key_messages = house_data.get("key_messages", [])
        benefits = [m["content"] for m in key_messages if m.get("section_type") == "benefit" or m.get("section_type") == "benefit_list"]
    for i in range(1, 6):
        placeholders[f"{{benefit_{i}}}"] = benefits[i-1] if i-1 < len(benefits) else ""

    objections = house_data.get("objections", [])
    for i in range(1, 6):
        placeholders[f"{{objection_{i}}}"] = objections[i-1] if i-1 < len(objections) else ""

    pillars = house_data.get("pillars", [])
    for i in range(1, 6):
        placeholders[f"{{pillar_{i}}}"] = pillars[i-1]["description"] if i-1 < len(pillars) else ""

    personas = house_data.get("personas", [])
    for i in range(1, 6):
        placeholders[f"{{persona_{i}}}"] = personas[i-1]["name"] if i-1 < len(personas) else ""

    for k, v in placeholders.items():
        if k in res:
            res = res.replace(k, str(v))
    return res

def _get_first_proof_point(house_data: dict) -> str:
    key_messages = house_data.get("key_messages", [])
    proof_points = [m["content"] for m in key_messages if m.get("section_type") == "proof_point"]
    return proof_points[0] if proof_points else ""

def truncate_to_token_budget(text: str, max_tokens: int = 150) -> str:
    """Rough token budget truncation (1 token ≈ 4 chars)."""
    max_chars = max_tokens * 4
    return text[:max_chars]
