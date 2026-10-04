"""Render the seed message houses as Markdown source documents.

Output goes to seed_data/documents/ and is meant to be dropped into the synced
Drive folder, so the demo instance can be populated through the real ingestion
path (structure.py's HouseStructurer) rather than only by direct seeding.

Headings are chosen to match src/pipeline/structure.py's section_map, so a
round trip through ingestion reproduces roughly the same typed key messages.

    python -m seed_data.export_documents
"""

import pathlib
from datetime import datetime

from seed_data.seed import (
    _acme_cloud_security, _helix_hr, _apex_financial_analytics,
    _clarity_cms, _forge_devops, _nexus_supply_chain,
    _pulse_customer_success, _solara_energy_management,
    _vantage_sales_intelligence, _atlas_knowledge_management,
)

#: SectionType value -> document heading. structure.py's section_map keys off these.
TYPE_HEADING: dict[str, str] = {
    "headline":     "Headlines",
    "subhead":      "Subheads",
    "benefit":      "Benefits",
    "use_case":     "Use Cases",
    "proof_point":  "Proof Points",
    "objection":    "Objections",
    "social_proof": "Social Proof",
}

OUT_DIR = pathlib.Path(__file__).parent / "documents"

_HOUSE_BUILDERS = [
    _acme_cloud_security, _helix_hr, _apex_financial_analytics,
    _clarity_cms, _forge_devops, _nexus_supply_chain,
    _pulse_customer_success, _solara_energy_management,
    _vantage_sales_intelligence, _atlas_knowledge_management,
]


def _val(enum_or_str) -> str:
    """Enum members stringify as 'SectionType.HEADLINE', which matches no
    heading key — always take .value."""
    return getattr(enum_or_str, "value", str(enum_or_str))


def render(house_data: dict) -> str:
    house = house_data["house"]
    lines = [f"# {house.name}", "", house.summary, ""]
    if house.positioning:
        lines += ["## Positioning", house.positioning, ""]
    if house.audience:
        lines += ["## Target Audience", house.audience, ""]
    if house.tagline:
        lines += ["## Tagline", house.tagline, ""]
    if house.differentiation:
        lines += ["## Differentiation", house.differentiation, ""]

    grouped: dict[str, list[tuple[str, int]]] = {}
    for msg in house_data["messages"]:
        grouped.setdefault(_val(msg.section_type), []).append((msg.content, msg.priority))

    if grouped:
        lines.append("## Key Messages")
        lines.append("")
        for t, heading in TYPE_HEADING.items():
            if t not in grouped:
                continue
            by_priority = sorted(grouped[t], key=lambda x: x[1])
            lines.append(f"### {heading} (Priority {by_priority[0][1]}-{by_priority[-1][1]})")
            for content, _priority in by_priority:
                lines.append(f"- {content}")
            lines.append("")

    personas = house_data.get("personas", [])
    if personas:
        lines.append("## Personas")
        lines.append("")
        for persona in personas:
            lines += [f"### {persona.name}", persona.description, ""]
            if persona.objections:
                lines.append("**Objections:**")
                for obj in persona.objections:
                    lines.append(f"- {obj}")
                lines.append("")

    return "\n".join(lines)


def export() -> list[pathlib.Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    now = datetime.utcnow()
    for build in _HOUSE_BUILDERS:
        item = build(now)
        house = item["house"]
        path = OUT_DIR / f"{house.name}.md"
        path.write_text(render(item), encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for p in export():
        print(f"{p.relative_to(pathlib.Path.cwd())}  {p.stat().st_size} bytes")
