"""Design system: schema v2, templates, and rendering."""

from src.design.schema_v2 import DesignSpec, PageSpec, PagePreset, Zone, ZoneType, TextStyle, Emphasis, Orientation
from src.design.template_registry import Template, TemplateRegistry, seed_default_templates

__all__ = [
    "DesignSpec", "PageSpec", "PagePreset", "Zone", "ZoneType",
    "TextStyle", "Emphasis", "Orientation",
    "Template", "TemplateRegistry", "seed_default_templates",
]
