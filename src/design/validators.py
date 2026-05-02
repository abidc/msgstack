"""Pydantic validation for visual design specifications (Schema v2)."""

from pydantic import BaseModel, validator, Field
from typing import Optional, Literal
import json


class ZoneContent(BaseModel):
    """Content for a single zone in a design template."""

    text: str = ""
    items: list[str] = Field(default_factory=list)
    image_id: Optional[str] = None
    image_url: Optional[str] = None
    style: dict = Field(default_factory=dict)


class Zone(BaseModel):
    """A single zone in a design template."""

    id: str
    type: str  # hero, positioning, message_list, pillar_grid, proof_block, persona_strip, etc.
    capacity: int = 1  # max number of items/lines
    max_chars: int = 500
    content: Optional[ZoneContent] = None
    x: float = 0
    y: float = 0
    width: float = 100
    height: float = 100
    z_index: int = 0
    visible: bool = True


class DesignSpec(BaseModel):
    """Full design specification matching Schema v2."""

    version: str = "2.0"
    artifact_type: str
    template_id: str
    zones: list[Zone] = Field(default_factory=list)
    canvas_width: int = 800
    canvas_height: int = 1200
    background: dict = Field(default_factory=lambda: {"type": "solid", "color": "#FFFFFF"})
    metadata: dict = Field(default_factory=dict)

    @validator('zones')
    def validate_zones(cls, v):
        """Ensure zone IDs are unique."""
        ids = [z.id for z in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Zone IDs must be unique")
        return v

    def get_zone(self, zone_id: str) -> Optional[Zone]:
        """Get a zone by ID."""
        for z in self.zones:
            if z.id == zone_id:
                return z
        return None

    def get_zones_by_type(self, zone_type: str) -> list[Zone]:
        """Get all zones of a given type."""
        return [z for z in self.zones if z.type == zone_type]


def validate_and_fill_design_spec(
    raw_json: str,
    template_zones: list[dict],
    house_data: dict,
) -> DesignSpec:
    """
    Validate LLM output against Schema v2.
    - Parse JSON
    - Validate with Pydantic
    - Auto-fill missing optional fields with template defaults
    - Fallback fill: inject template default content from messaging house if LLM omits required zone
    - Token budget guardrail: truncate oversized text blocks
    """
    try:
        parsed = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in design spec: {e}")

    # Build template zone lookup
    template_zone_map = {z.get("id"): z for z in template_zones}

    # Ensure all template zones exist in output
    zones_out = parsed.get("zones", [])

    # Build zone type → content mapping from house data for fallback
    zone_content_map = _build_zone_content_map(house_data)

    # Check for missing required zones and inject defaults
    existing_ids = {z.get("id") for z in zones_out}
    for tz in template_zones:
        if tz.get("required", False) and tz["id"] not in existing_ids:
            # Inject default content from house data
            default_content = zone_content_map.get(tz["type"], {})
            zones_out.append({
                "id": tz["id"],
                "type": tz["type"],
                "capacity": tz.get("capacity", 1),
                "max_chars": tz.get("max_chars", 500),
                "content": default_content,
                "x": tz.get("x", 0),
                "y": tz.get("y", 0),
                "width": tz.get("width", 100),
                "height": tz.get("height", 100),
                "z_index": tz.get("z_index", 0),
                "visible": tz.get("visible", True),
            })

    # Apply token budget guardrail - truncate oversized content
    for zone in zones_out:
        max_chars = zone.get("max_chars", 500)
        content = zone.get("content")
        if content and isinstance(content, dict):
            if "text" in content and content["text"]:
                content["text"] = content["text"][:max_chars]
            if "items" in content and isinstance(content["items"], list):
                content["items"] = [item[:max_chars] for item in content["items"][:zone.get("capacity", 10)]]

    parsed["zones"] = zones_out

    # Validate with Pydantic
    spec = DesignSpec(**parsed)

    return spec


def _build_zone_content_map(house_data: dict) -> dict:
    """
    Build mapping of zone_type → default content from messaging house.
    Maps:
    - tagline → hero.text_content
    - positioning → hero.body
    - differentiation → pillar_grid
    - top 6 key messages by priority → message_list
    - personas → persona_strip
    - proof points → proof_block
    """
    mapping = {}

    # Tagline for hero zone
    if house_data.get("tagline"):
        mapping["hero"] = {"text": house_data["tagline"][:50]}

    # Positioning for body zones
    if house_data.get("positioning"):
        mapping["positioning"] = {"text": house_data["positioning"][:500]}

    # Differentiation for pillar_grid
    if house_data.get("differentiation"):
        diff_items = [item.strip() for item in house_data["differentiation"].split(".") if item.strip()][:3]
        mapping["pillar_grid"] = {"items": diff_items}

    # Top key messages for message_list (max 6)
    key_messages = house_data.get("key_messages", [])
    if key_messages:
        sorted_msgs = sorted(key_messages, key=lambda x: x.get("priority", 3))[:6]
        mapping["message_list"] = {"items": [m["content"] for m in sorted_msgs]}

    # Personas for persona_strip (max 3, primary first)
    personas = house_data.get("personas", [])
    if personas:
        sorted_personas = sorted(personas, key=lambda x: 0 if x.get("is_primary") else 1)[:3]
        mapping["persona_strip"] = {"items": [p["name"] for p in sorted_personas]}

    # Proof points for proof_block (max 3)
    proof_points = [m for m in key_messages if m.get("section_type") == "proof_point"]
    if proof_points:
        sorted_proof = sorted(proof_points, key=lambda x: x.get("priority", 3))[:3]
        mapping["proof_block"] = {"items": [p["content"] for p in sorted_proof]}

    return mapping


def truncate_to_token_budget(text: str, max_tokens: int = 150) -> str:
    """Rough token budget truncation (1 token ≈ 4 chars)."""
    max_chars = max_tokens * 4
    return text[:max_chars]
