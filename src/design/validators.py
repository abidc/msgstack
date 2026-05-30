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
    template_page_spec: Optional[dict] = None,
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

    # Normalize template_zones to Zone models
    normalized_template_zones = []
    for tz in template_zones:
        if isinstance(tz, dict):
            normalized_template_zones.append(Zone(**tz))
        else:
            normalized_template_zones.append(tz)
    template_zones = normalized_template_zones

    # Ensure zones list exists
    zones_out = parsed.get("zones", [])
    if not isinstance(zones_out, list):
        zones_out = []

    # Map zones by ID
    existing_zones = {}
    for z in zones_out:
        if isinstance(z, dict) and "id" in z:
            # Normalize legacy content struct
            if "content" in z and isinstance(z["content"], dict):
                cnt = z["content"]
                if "text" in cnt and "text_content" not in z:
                    z["text_content"] = cnt["text"]
                if "items" in cnt and "list_items" not in z:
                    z["list_items"] = cnt["items"]
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
            # Zone exists, apply constraint truncation and resolve placeholders
            z_dict = existing_zones[tz.id]
            if "text_content" in z_dict and isinstance(z_dict["text_content"], str):
                z_dict["text_content"] = _resolve_placeholder(z_dict["text_content"], house_data)[:1000]
            if "list_items" in z_dict and isinstance(z_dict["list_items"], list):
                z_dict["list_items"] = [_resolve_placeholder(str(item), house_data)[:500] for item in z_dict["list_items"]]

    parsed["zones"] = zones_out

    # Ensure page_spec exists and defaults from template_page_spec
    if "page_spec" not in parsed or not parsed["page_spec"]:
        if template_page_spec:
            parsed["page_spec"] = template_page_spec.model_dump() if hasattr(template_page_spec, "model_dump") else dict(template_page_spec)
        else:
            parsed["page_spec"] = PageSpec.from_preset(PagePreset.LETTER).model_dump()
    else:
        # Merge missing keys from template_page_spec
        t_spec = {}
        if template_page_spec:
            t_spec = template_page_spec.model_dump() if hasattr(template_page_spec, "model_dump") else dict(template_page_spec)
        for k, v in t_spec.items():
            if k not in parsed["page_spec"] or parsed["page_spec"][k] is None:
                parsed["page_spec"][k] = v

    # Validate and return
    return DesignSpec(**parsed)

def _resolve_placeholder(text: str, house_data: dict) -> str:
    """Helper to resolve placeholders like {positioning} from house_data."""
    if not text:
        return text
    res = text
    
    # Safely get key_messages
    key_messages_raw = house_data.get("structured_key_messages") or house_data.get("key_messages") or []
    key_messages = []
    if isinstance(key_messages_raw, list):
        for m in key_messages_raw:
            if isinstance(m, dict):
                key_messages.append(m)
            elif hasattr(m, "section_type") and hasattr(m, "content"):
                key_messages.append({"section_type": str(m.section_type), "content": m.content})
    
    # Safely get proof point
    proof_points = [m["content"] for m in key_messages if isinstance(m, dict) and str(m.get("section_type")).split(".")[-1].lower() == "proof_point"]
    first_proof = proof_points[0] if proof_points else ""
    if not first_proof and isinstance(house_data.get("primary_message"), str):
        first_proof = house_data.get("primary_message")

    placeholders = {
        "{house_name}": house_data.get("house_name") or house_data.get("name") or "",
        "{tagline}": house_data.get("tagline") or "",
        "{positioning}": house_data.get("positioning") or "",
        "{differentiation}": house_data.get("differentiation") or "",
        "{proof_point}": first_proof,
        "{competitor}": house_data.get("competitor") or "Competitor",
    }
    
    # Handlers for list item placeholders
    benefits = house_data.get("benefits") or []
    if not benefits:
        benefits = [m["content"] for m in key_messages if isinstance(m, dict) and str(m.get("section_type")).split(".")[-1].lower() in ("benefit", "benefit_list")]
    for i in range(1, 6):
        placeholders[f"{{benefit_{i}}}"] = benefits[i-1] if i-1 < len(benefits) else ""

    objections = house_data.get("objections") or []
    if not objections:
        # try to get from personas
        personas_raw = house_data.get("personas") or []
        for p in personas_raw:
            objs = p.get("objections") if isinstance(p, dict) else getattr(p, "objections", [])
            for ob in (objs or []):
                if isinstance(ob, dict):
                    objections.append(ob.get("statement", str(ob)))
                else:
                    objections.append(str(ob))
    for i in range(1, 6):
        placeholders[f"{{objection_{i}}}"] = objections[i-1] if i-1 < len(objections) else ""

    pillars = house_data.get("pillars") or []
    for i in range(1, 6):
        desc = ""
        if i-1 < len(pillars):
            p = pillars[i-1]
            desc = p.get("description") if isinstance(p, dict) else getattr(p, "description", str(p))
        placeholders[f"{{pillar_{i}}}"] = desc

    personas = house_data.get("personas") or []
    for i in range(1, 6):
        p_name = ""
        if i-1 < len(personas):
            p = personas[i-1]
            p_name = p.get("name") if isinstance(p, dict) else getattr(p, "name", str(p))
        placeholders[f"{{persona_{i}}}"] = p_name

    for k, v in placeholders.items():
        if k in res:
            res = res.replace(k, str(v))
    return res

def truncate_to_token_budget(text: str, max_tokens: int = 150) -> str:
    """Rough token budget truncation (1 token ≈ 4 chars)."""
    max_chars = max_tokens * 4
    return text[:max_chars]

