"""Render the seed corpus as Markdown source documents.

Output goes to seed_data/documents/ and is meant to be dropped into the synced
Drive folder, so the demo instance can be populated through the real ingestion
path rather than only by direct seeding.

Headings are chosen to match the assertion types the structurer maps onto, so a
round trip through ingestion reproduces roughly the same typed assertions.

    python -m seed_data.export_documents
"""

import pathlib

from seed_data.seed import CORPUS, EDGES

#: assertion_type -> document heading. The structurer keys off these.
TYPE_HEADING: dict[str, str] = {
    "constraint":         "Constraints",
    "sla":                "Service Level Objectives",
    "deprecation":        "Deprecations",
    "config_default":     "Configuration Defaults",
    "dependency":         "Dependencies",
    "capability":         "Capabilities",
    "limitation":         "Known Limitations",
    "security_posture":   "Security Posture",
    "interface_contract": "Interface Contract",
    "version_policy":     "Version Policy",
    "runbook_step":       "Runbook",
    "decision":           "Decisions",
}

OUT_DIR = pathlib.Path(__file__).parent / "documents"


def _val(enum_or_str) -> str:
    """Enum members stringify as 'AssertionType.CONSTRAINT', which matches no
    heading key — always take .value."""
    return getattr(enum_or_str, "value", str(enum_or_str))


def render(item: dict) -> str:
    spec = item["spec"]
    lines = [f"# {spec.name}", "", spec.summary, ""]
    if spec.positioning:
        lines += ["## Overview", spec.positioning, ""]

    grouped: dict[str, list[tuple[str, str]]] = {}
    for a_type, content, _tier, status, _tag in item["assertions"]:
        grouped.setdefault(_val(a_type), []).append((content, _val(status)))

    for t, heading in TYPE_HEADING.items():
        if t not in grouped:
            continue
        lines.append(f"## {heading}")
        for content, status in grouped[t]:
            lines.append(f"- {content}" + (" **[LOCKED]**" if status == "locked" else ""))
        lines.append("")

    if item["audiences"]:
        lines.append("## Audiences")
        for name, desc, qa in item["audiences"]:
            lines += [f"### {name}", desc, ""]
            for statement, response in qa:
                lines += [f"**Q: {statement}**", f"A: {response}", ""]

    deps = sorted({(rel, dst) for src, _, rel, dst, _ in EDGES if src == spec.name})
    if deps:
        lines.append("## Related Specs")
        lines += [f"- {rel} → {dst}" for rel, dst in deps]
        lines.append("")

    return "\n".join(lines)


def export() -> list[pathlib.Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for item in CORPUS:
        path = OUT_DIR / f"{item['spec'].name}.md"
        path.write_text(render(item), encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for p in export():
        print(f"{p.relative_to(pathlib.Path.cwd())}  {p.stat().st_size} bytes")
