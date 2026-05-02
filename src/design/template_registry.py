"""Artifact Template Registry — maps artifact types to DesignSpec layouts."""

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from src.design.schema_v2 import (
    DesignSpec,
    PagePreset,
    PageSpec,
    Zone,
    ZoneType,
    TextStyle,
    Emphasis,
)


TEMPLATE_DIR = Path("data/templates")


class Template(BaseModel):
    artifact_type: str
    page_spec: PageSpec
    zones: list[Zone] = []
    brand_zones: list[str] = []


class TemplateRegistry:
    def __init__(self, template_dir: Path | None = None):
        self.template_dir = template_dir or TEMPLATE_DIR
        self.template_dir.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> list[dict]:
        templates = []
        for f in self.template_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                templates.append({
                    "artifact_type": data.get("artifact_type", f.stem),
                    "file": f.name,
                    "zone_count": len(data.get("zones", [])),
                })
            except Exception:
                pass
        return sorted(templates, key=lambda x: x["artifact_type"])

    def get_template(self, artifact_type: str) -> Template | None:
        for candidate in [
            self.template_dir / f"{artifact_type}.json",
            self.template_dir / f"{artifact_type.replace('_', '-')}.json",
            self.template_dir / f"{artifact_type.replace(' ', '_')}.json",
        ]:
            if candidate.exists():
                data = json.loads(candidate.read_text())
                return Template(**data)
        return None

    def register_template(self, template: Template) -> None:
        file_path = self.template_dir / f"{template.artifact_type}.json"
        file_path.write_text(template.model_dump_json(indent=2))

    def load_all(self) -> dict[str, Template]:
        result = {}
        for f in self.template_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                t = Template(**data)
                result[t.artifact_type] = t
            except Exception:
                pass
        return result


def build_datasheet_template() -> Template:
    page = PageSpec.from_preset(PagePreset.LETTER)
    zones = [
        Zone(
            id="header", type=ZoneType.HEADER, row=0, col=0, colspan=3,
            text_content="{house_name} | {tagline}",
            text_style=TextStyle.HEADING, emphasis=Emphasis.PRIMARY,
            brand_refs=["brand"],
        ),
        Zone(
            id="hero", type=ZoneType.HERO, row=1, col=0, colspan=3,
            text_content="{positioning}",
            text_style=TextStyle.HEADING, emphasis=Emphasis.PRIMARY,
        ),
        Zone(
            id="benefits_grid", type=ZoneType.PILLAR_GRID, row=2, col=0, colspan=3,
            text_content="Key Benefits",
            text_style=TextStyle.HEADING, emphasis=Emphasis.SECONDARY,
            list_items=["{benefit_1}", "{benefit_2}", "{benefit_3}"],
        ),
        Zone(
            id="proof", type=ZoneType.PROOF_BLOCK, row=3, col=0, colspan=2,
            text_content="{proof_point}",
            text_style=TextStyle.BODY, emphasis=Emphasis.MUTED,
        ),
        Zone(
            id="cta_footer", type=ZoneType.CTA_FOOTER, row=4, col=0, colspan=3,
            text_content="Contact us today to learn more.",
            text_style=TextStyle.BODY, emphasis=Emphasis.PRIMARY,
            brand_refs=["brand"],
        ),
    ]
    return Template(
        artifact_type="datasheet",
        page_spec=page,
        zones=zones,
        brand_zones=["header", "cta_footer"],
    )


def build_battlecard_template() -> Template:
    page = PageSpec.from_preset(PagePreset.LETTER)
    zones = [
        Zone(
            id="header", type=ZoneType.HEADER, row=0, col=0, colspan=3,
            text_content="{house_name} vs {competitor}",
            text_style=TextStyle.HEADING, emphasis=Emphasis.PRIMARY,
            brand_refs=["brand"],
        ),
        Zone(
            id="positioning", type=ZoneType.POSITIONING_BLOCK, row=1, col=0, colspan=3,
            text_content="{positioning}",
            text_style=TextStyle.HEADING, emphasis=Emphasis.PRIMARY,
        ),
        Zone(
            id="objection_handler", type=ZoneType.MESSAGE_LIST, row=2, col=0, colspan=2,
            text_content="Overcoming Objections",
            text_style=TextStyle.HEADING,
            list_items=["{objection_1}", "{objection_2}", "{objection_3}"],
        ),
        Zone(
            id="proof", type=ZoneType.PROOF_BLOCK, row=3, col=0, colspan=3,
            text_content="{proof_point}",
            text_style=TextStyle.BODY, emphasis=Emphasis.MUTED,
        ),
        Zone(
            id="cta_footer", type=ZoneType.CTA_FOOTER, row=4, col=0, colspan=3,
            text_content="Choose {house_name} — the smarter choice.",
            text_style=TextStyle.BODY, emphasis=Emphasis.PRIMARY,
            brand_refs=["brand"],
        ),
    ]
    return Template(
        artifact_type="battlecard",
        page_spec=page,
        zones=zones,
        brand_zones=["header", "cta_footer"],
    )


def build_social_card_template() -> Template:
    page = PageSpec.from_preset(PagePreset.WIDE_16_9)
    zones = [
        Zone(
            id="header", type=ZoneType.HEADER, row=0, col=0, colspan=4,
            text_content="{house_name}",
            text_style=TextStyle.HEADING, emphasis=Emphasis.PRIMARY,
            brand_refs=["brand"],
        ),
        Zone(
            id="hero", type=ZoneType.HERO, row=1, col=0, colspan=4,
            text_content="{headline}",
            text_style=TextStyle.HEADING, emphasis=Emphasis.PRIMARY,
        ),
        Zone(
            id="subhead", type=ZoneType.MESSAGE_LIST, row=2, col=0, colspan=4,
            text_content="",
            text_style=TextStyle.BODY,
            list_items=["{subhead_1}", "{subhead_2}"],
        ),
        Zone(
            id="cta_footer", type=ZoneType.CTA_FOOTER, row=3, col=0, colspan=4,
            text_content="{tagline}",
            text_style=TextStyle.CAPTION, emphasis=Emphasis.SECONDARY,
            brand_refs=["brand"],
        ),
    ]
    return Template(
        artifact_type="social_card",
        page_spec=page,
        zones=zones,
        brand_zones=["header", "cta_footer"],
    )


def build_executive_summary_template() -> Template:
    page = PageSpec.from_preset(PagePreset.LETTER)
    zones = [
        Zone(
            id="header", type=ZoneType.HEADER, row=0, col=0, colspan=3,
            text_content="{house_name} | Executive Summary",
            text_style=TextStyle.HEADING, emphasis=Emphasis.PRIMARY,
            brand_refs=["brand"],
        ),
        Zone(
            id="positioning", type=ZoneType.POSITIONING_BLOCK, row=1, col=0, colspan=3,
            text_content="{positioning}",
            text_style=TextStyle.HEADING, emphasis=Emphasis.PRIMARY,
        ),
        Zone(
            id="pillars", type=ZoneType.PILLAR_GRID, row=2, col=0, colspan=3,
            text_content="Strategic Pillars",
            text_style=TextStyle.HEADING,
            list_items=["{pillar_1}", "{pillar_2}", "{pillar_3}"],
        ),
        Zone(
            id="persona_strip", type=ZoneType.PERSONA_STRIP, row=3, col=0, colspan=3,
            text_content="Target Audience",
            text_style=TextStyle.BODY,
            list_items=["{persona_1}", "{persona_2}"],
        ),
        Zone(
            id="proof", type=ZoneType.PROOF_BLOCK, row=4, col=0, colspan=2,
            text_content="{proof_point}",
            text_style=TextStyle.BODY, emphasis=Emphasis.MUTED,
        ),
        Zone(
            id="cta_footer", type=ZoneType.CTA_FOOTER, row=5, col=0, colspan=3,
            text_content="Learn more at {house_name}.com",
            text_style=TextStyle.BODY, emphasis=Emphasis.PRIMARY,
            brand_refs=["brand"],
        ),
    ]
    return Template(
        artifact_type="executive_summary",
        page_spec=page,
        zones=zones,
        brand_zones=["header", "cta_footer"],
    )


def seed_default_templates(registry: TemplateRegistry | None = None) -> None:
    """Write all built-in templates to disk if they don't exist."""
    reg = registry or TemplateRegistry()
    builders = {
        "datasheet": build_datasheet_template,
        "battlecard": build_battlecard_template,
        "social_card": build_social_card_template,
        "executive_summary": build_executive_summary_template,
    }
    for name, builder in builders.items():
        file_path = reg.template_dir / f"{name}.json"
        if not file_path.exists():
            template = builder()
            reg.register_template(template)
