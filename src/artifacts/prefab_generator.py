"""Prefab artifact generator — builds Prefab component trees from skill output."""

from uuid import UUID

from prefab_ui import PrefabApp
from prefab_ui.components import (
    Badge,
    Button,
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
    Column,
    Div,
    H3,
    H4,
    Muted,
    P,
    Page,
    Row,
    Separator,
    Text,
)
from prefab_ui.actions.mcp import SendMessage, CallTool

from src.store import Store


def build_artifact_preview(skill_id: str, sections: dict, spec_name: str, spec_id: str) -> PrefabApp:
    """Build a Prefab component tree from skill-generated sections."""
    
    if skill_id == "one_pager":
        return _build_one_pager(sections, spec_name, spec_id)
    elif skill_id == "linkedin_post":
        return _build_linkedin_post(sections, spec_name, spec_id)
    elif skill_id == "email_template":
        return _build_email_template(sections, spec_name, spec_id)
    elif skill_id == "battlecard":
        return _build_battlecard(sections, spec_name, spec_id)
    elif skill_id == "press_release":
        return _build_press_release(sections, spec_name, spec_id)
    elif skill_id == "blog_post":
        return _build_blog_post(sections, spec_name, spec_id)
    elif skill_id == "faq_document":
        return _build_faq(sections, spec_name, spec_id)
    else:
        return _build_generic(sections, spec_name, spec_id)


def _section_text(val):
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return "\n".join(str(v) for v in val)
    return str(val)


def _build_one_pager(sections: dict, spec_name: str, spec_id: str) -> PrefabApp:
    with Page(title=f"One-Pager: {spec_name}") as view:
        with Card():
            with CardHeader():
                CardTitle(spec_name)
                Muted("Generated from messaging framework")
        
        for key, label in [("positioning", "Positioning"), ("tagline", "Tagline"), ("differentiation", "Differentiation")]:
            if key in sections:
                with Card():
                    with CardHeader():
                        CardTitle(label)
                    with CardContent():
                        P(_section_text(sections[key]))
        
        if "assertions" in sections:
            with Card():
                with CardHeader():
                    CardTitle("Key Messages")
                with CardContent():
                    msgs = sections["assertions"]
                    if isinstance(msgs, list):
                        for m in msgs[:5]:
                            with Row(gap=2, wrap=True):
                                Badge("•", variant="default")
                                Text(str(m)[:100])
                    else:
                        P(_section_text(msgs)[:300])
        
        with Card():
            with CardFooter():
                with Row(gap=2):
                    Button("Copy to Clipboard", variant="outline", on_click=SendMessage(f"One-pager for {spec_name}:\n\n{_section_text(sections.get('positioning', ''))}"))
                    Button("Generate Another", variant="default", on_click=CallTool("generate_artifact", arguments={"skill_id": "one_pager", "spec_id": spec_id}))

    return PrefabApp(view=view, title=f"One-Pager: {spec_name}")


def _build_linkedin_post(sections: dict, spec_name: str, spec_id: str) -> PrefabApp:
    content = _section_text(sections.get("body") or sections.get("content") or "")
    
    with Page(title=f"LinkedIn Post: {spec_name}") as view:
        with Card():
            with CardHeader():
                with Row(align="center", gap=2):
                    Badge("LinkedIn", variant="default")
                    CardTitle("Social Post")
            with CardContent():
                P(content)
            with CardFooter():
                with Row(gap=2):
                    Button("Use This Post", variant="outline", on_click=SendMessage(content))
                    Button("Rewrite", variant="ghost", on_click=CallTool("generate_artifact", arguments={"skill_id": "linkedin_post", "spec_id": spec_id}))

    return PrefabApp(view=view, title=f"LinkedIn Post: {spec_name}")


def _build_email_template(sections: dict, spec_name: str, spec_id: str) -> PrefabApp:
    subject = _section_text(sections.get("subject", ""))
    body = _section_text(sections.get("body", ""))
    cta = _section_text(sections.get("cta", ""))
    
    with Page(title=f"Email: {spec_name}") as view:
        with Card():
            with CardHeader():
                CardTitle("Email Template")
            with CardContent():
                with Column(gap=3):
                    with Card():
                        with CardHeader():
                            H4("Subject Line")
                        with CardContent():
                            P(subject)
                    
                    with Card():
                        with CardHeader():
                            H4("Body")
                        with CardContent():
                            P(body)
                    
                    with Card():
                        with CardHeader():
                            H4("CTA")
                        with CardContent():
                            P(cta)
        
        with Card():
            with CardFooter():
                with Row(gap=2):
                    Button("Use Template", variant="outline", on_click=SendMessage(f"Subject: {subject}\n\n{body}\n\n{cta}"))
                    Button("Regenerate", variant="default", on_click=CallTool("generate_artifact", arguments={"skill_id": "email_template", "spec_id": spec_id}))

    return PrefabApp(view=view, title=f"Email Template: {spec_name}")


def _build_battlecard(sections: dict, spec_name: str, spec_id: str) -> PrefabApp:
    competitor = _section_text(sections.get("competitor", "Unknown"))
    strengths = sections.get("our_strengths", [])
    weaknesses = sections.get("their_weaknesses", [])
    
    with Page(title=f"Battlecard: {competitor}") as view:
        with Card():
            with CardHeader():
                with Row(align="center", gap=2):
                    Badge("Competitive", variant="default")
                    CardTitle(f"vs {competitor}")
        
        if strengths:
            with Card():
                with CardHeader():
                    H4("Our Strengths")
                with CardContent():
                    for s in (strengths if isinstance(strengths, list) else [strengths])[:4]:
                        with Row(gap=2, wrap=True):
                            Badge("+", variant="success")
                            Text(str(s)[:120])
        
        if weaknesses:
            with Card():
                with CardHeader():
                    H4("Their Weaknesses")
                with CardContent():
                    for w in (weaknesses if isinstance(weaknesses, list) else [weaknesses])[:3]:
                        with Row(gap=2, wrap=True):
                            Badge("-", variant="warning")
                            Text(str(w)[:120])
        
        with Card():
            with CardFooter():
                Button("Copy Battlecard", variant="outline", on_click=SendMessage(f"Battlecard vs {competitor}:\n\nStrengths: {strengths}\n\nWeaknesses: {weaknesses}"))

    return PrefabApp(view=view, title=f"Battlecard: {competitor}")


def _build_press_release(sections: dict, spec_name: str, spec_id: str) -> PrefabApp:
    headline = _section_text(sections.get("headline", ""))
    lead = _section_text(sections.get("lead") or sections.get("body", ""))
    
    with Page(title=f"Press Release: {spec_name}") as view:
        with Card():
            with CardHeader():
                Badge("Press Release", variant="default")
                H3(headline)
            with CardContent():
                P(lead[:500])
            with CardFooter():
                with Row(gap=2):
                    Button("Copy PR", variant="outline", on_click=SendMessage(f"{headline}\n\n{lead}"))
                    Button("Regenerate", variant="ghost", on_click=CallTool("generate_artifact", arguments={"skill_id": "press_release", "spec_id": spec_id}))

    return PrefabApp(view=view, title=f"Press Release: {spec_name}")


def _build_blog_post(sections: dict, spec_name: str, spec_id: str) -> PrefabApp:
    title = _section_text(sections.get("title", ""))
    intro = _section_text(sections.get("intro") or sections.get("introduction", ""))
    
    with Page(title=f"Blog Post: {spec_name}") as view:
        with Card():
            with CardHeader():
                Badge("Blog Post", variant="default")
                H3(title)
            with CardContent():
                with Column(gap=2):
                    H4("Introduction")
                    P(intro[:400])
            with CardFooter():
                Button("Copy Draft", variant="outline", on_click=SendMessage(f"{title}\n\n{intro}"))

    return PrefabApp(view=view, title=f"Blog Post: {spec_name}")


def _build_faq(sections: dict, spec_name: str, spec_id: str) -> PrefabApp:
    qa_pairs = []
    for key, val in sections.items():
        if key.lower().startswith("q"):
            qa_pairs.append({"q": _section_text(val), "a": ""})
        elif key.lower().startswith("a") and qa_pairs:
            qa_pairs[-1]["a"] = _section_text(val)
    
    with Page(title=f"FAQ: {spec_name}") as view:
        with Card():
            with CardHeader():
                Badge("FAQ Document", variant="default")
                CardTitle("Frequently Asked Questions")
            with CardContent():
                with Column(gap=3):
                    for i, pair in enumerate(qa_pairs[:8]):
                        with Card():
                            with CardContent():
                                P(f"Q: {pair.get('q', '')}")
                                if pair.get('a'):
                                    Muted(f"A: {pair['a'][:200]}")

    return PrefabApp(view=view, title=f"FAQ: {spec_name}")


def _build_generic(sections: dict, spec_name: str, spec_id: str) -> PrefabApp:
    with Page(title=f"Artifact: {spec_name}") as view:
        with Card():
            with CardHeader():
                CardTitle(f"Generated: {spec_name}")
            with CardContent():
                with Column(gap=2):
                    for key, val in sections.items():
                        with Card():
                            with CardHeader():
                                H4(key.replace("_", " ").title())
                            with CardContent():
                                P(_section_text(val)[:300])

    return PrefabApp(view=view, title=f"Artifact: {spec_name}")
