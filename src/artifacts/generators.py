"""Prefab artifact generators — clean context-manager-based component trees."""

from uuid import UUID

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
    DataTable,
    DataTableColumn,
    Div,
    H3,
    H4,
    Muted,
    P,
    Row,
    Separator,
    Text,
    View,
)
from prefab_ui.actions.mcp import CallTool, SendMessage

from src.store import Store
from src.models import SectionType


def _get_store() -> Store:
    store = Store()
    store.init()
    return store


def build_one_pager(house_id: str, app_config=None):
    from prefab_ui import PrefabApp

    store = _get_store()
    house = store.get_house(UUID(house_id))
    if not house:
        return {"error": f"House {house_id} not found"}
    messages = store.get_key_messages(UUID(house_id))
    personas = store.get_personas(UUID(house_id))

    table_data = [
        {
            "section": m.section_type.value.title(),
            "message": m.content[:100] + ("..." if len(m.content) > 100 else ""),
            "priority": str(m.priority),
            "channels": ", ".join(c.value for c in m.channels),
        }
        for m in messages
    ]

    with View(title=house.name, gap=4) as view:
        with Card():
            with CardHeader():
                with Row(align="center", gap=3):
                    CardTitle(house.name)
                    if house.status:
                        Badge(house.status.upper(), variant="outline")
                if house.audience:
                    Muted(house.audience[:120])

        with Card():
            with CardHeader():
                CardTitle("Positioning")
            with CardContent():
                P(house.positioning[:500] if house.positioning else "Not set")
                if house.tagline:
                    with Row(gap=2, wrap=True):
                        Badge("Tagline: " + house.tagline, variant="default")
                if house.differentiation:
                    Muted(house.differentiation[:300] + ("..." if len(house.differentiation) > 300 else ""))

        with Card():
            with CardHeader():
                CardTitle("Key Messages")
            with CardContent():
                with Column(gap=3):
                    for section in SectionType:
                        msgs = [m for m in messages if m.section_type == section]
                        if not msgs:
                            continue
                        with Column(gap=2):
                            H4(section.value.title())
                            for msg in msgs[:3]:
                                with Row(gap=2, wrap=True, align="center"):
                                    Badge(str(msg.priority), variant="outline")
                                    Text(msg.content[:120] + ("..." if len(msg.content) > 120 else ""))

        with Card():
            with CardHeader():
                CardTitle("Personas")
            with CardContent():
                with Row(gap=3, wrap=True):
                    for p in personas:
                        with Card():
                            with CardHeader():
                                CardTitle(p.name)
                            with CardContent():
                                P(p.description[:200] + ("..." if len(p.description) > 200 else ""))
                                if p.pain_points:
                                    with Column(gap=1):
                                        Muted("Pain points:")
                                        for pp in p.pain_points[:2]:
                                            Text("• " + pp[:80])

        if table_data:
            with Card():
                with CardHeader():
                    CardTitle("Message Inventory")
                with CardContent():
                    DataTable(
                        columns=[
                            DataTableColumn(key="section", header="Section", sortable=True),
                            DataTableColumn(key="message", header="Message"),
                            DataTableColumn(key="priority", header="Priority", sortable=True),
                            DataTableColumn(key="channels", header="Channels"),
                        ],
                        rows=table_data[:15],
                        paginated=True,
                        page_size=10,
                    )

        with Card():
            with CardFooter():
                with Row(gap=2, align="center"):
                    Button(
                        "Use This Messaging",
                        variant="outline",
                        on_click=SendMessage(f"Ground my next content in '{house.name}'"),
                    )
                    Button(
                        "Generate LinkedIn Post",
                        variant="default",
                        on_click=CallTool(
                            "generate_social_posts",
                            {"messaging_house_id": str(house.id), "channels": ["linkedin"]},
                        ),
                    )
                    Button(
                        "Generate Email",
                        variant="outline",
                        on_click=CallTool(
                            "generate_email_template",
                            {"messaging_house_id": str(house.id), "stage": "awareness"},
                        ),
                    )
                with Row(gap=2, align="center"):
                    Muted(
                        f"Last synced: {house.last_synced.strftime('%Y-%m-%d') if house.last_synced else 'Never'}"
                    )
                    Muted(f"• {len(messages)} messages • {len(personas)} personas")

    return PrefabApp(
        view=view,
        title=house.name,
        config=app_config,
    )


def build_social_posts(house_id: str, channels: list[str] = None, app_config=None):
    from prefab_ui import PrefabApp

    channels = channels or ["linkedin"]
    store = _get_store()
    house = store.get_house(UUID(house_id))
    if not house:
        return {"error": f"House {house_id} not found"}

    messages = store.get_key_messages(UUID(house_id))
    posts = []
    for i, msg in enumerate(messages[:9]):
        variant = msg.variants.get("linkedin") if msg.variants else None
        if not variant:
            continue
        posts.append(
            {
                "id": f"post-{i+1}",
                "channel": "LinkedIn",
                "section": msg.section_type.value.title(),
                "content": variant,
                "priority": msg.priority,
            }
        )

    with View(title=f"Social Posts — {house.name}", gap=4) as view:
        with Card():
            with CardHeader():
                with Row(align="center", gap=2):
                    CardTitle(f"Social Posts")
                    Badge(str(len(posts)), variant="outline")
            with CardContent():
                with Column(gap=3):
                    for post in posts:
                        with Card():
                            with CardHeader():
                                with Row(align="center", gap=2):
                                    Badge("LinkedIn", variant="default")
                                    Badge(post["section"], variant="outline")
                            with CardContent():
                                P(post["content"])
                            with CardFooter():
                                with Row(gap=2):
                                    Button(
                                        "Use This Post",
                                        variant="outline",
                                        on_click=SendMessage(post["content"]),
                                    )
                                    Button(
                                        "Rewrite",
                                        variant="ghost",
                                        on_click=CallTool(
                                            "search_messaging",
                                            {
                                                "query": f"linkedin {post['section']} for {house.name}",
                                                "section_types": [post["section"].lower()],
                                                "channels": ["linkedin"],
                                            },
                                        ),
                                    )

    return PrefabApp(view=view, title=house.name, config=app_config)


def build_email_template(house_id: str, stage: str = "awareness", app_config=None):
    from prefab_ui import PrefabApp

    stages = {"awareness": "Awareness", "consideration": "Consideration", "decision": "Decision"}
    stage_labels = stages.get(stage, "Awareness")

    store = _get_store()
    house = store.get_house(UUID(house_id))
    if not house:
        return {"error": f"House {house_id} not found"}

    messages = store.get_key_messages(UUID(house_id))
    benefits = [m for m in messages if m.section_type == SectionType.BENEFIT]
    headlines = [m for m in messages if m.section_type == SectionType.HEADLINE]

    stage_content = {
        "awareness": {
            "subject": (headlines[0].content[:70] if headlines else house.tagline or house.positioning[:70]),
            "hook": benefits[0].content if benefits else house.positioning,
            "body": f"With Acme CloudOps, {house.differentiation[:180]}...",
            "cta": "See how it works",
        },
        "consideration": {
            "subject": "What teams like yours are doing differently with cloud ops",
            "hook": "Teams running Acme report 60% less time on infra ops.",
            "body": f"{house.tagline} — {house.positioning[:150]}",
            "cta": "Book a 30-min demo",
        },
        "decision": {
            "subject": "40% cloud cost reduction, no refactoring required",
            "hook": benefits[0].variants.get("email", benefits[0].content) if benefits else "Ready to cut costs?",
            "body": f"We help companies like yours optimize cloud spend without touching your application. {house.differentiation[:150]}",
            "cta": "Start your free trial",
        },
    }

    content = stage_content.get(stage, stage_content["awareness"])

    with View(title=f"Email Template — {stage_labels}", gap=4) as view:
        with Card():
            with CardHeader():
                with Row(align="center", gap=2):
                    CardTitle(f"Email: {stage_labels} Stage")
                    Badge(stage.upper(), variant="default")
            with CardContent():
                with Column(gap=4):
                    with Card():
                        with CardHeader():
                            CardTitle("Subject Line")
                        with CardContent():
                            P(content["subject"])
                            with Row(gap=2):
                                Button(
                                    "Use Subject",
                                    variant="outline",
                                    on_click=SendMessage(f"Subject: {content['subject']}"),
                                )
                                Button(
                                    "Rewrite Subject",
                                    variant="ghost",
                                    on_click=CallTool(
                                        "search_messaging",
                                        {
                                            "query": f"email subject {stage} for {house.name}",
                                            "section_types": ["headline", "subhead"],
                                            "channels": ["email"],
                                        },
                                    ),
                                )

                    with Card():
                        with CardHeader():
                            CardTitle("Hook / Opening")
                        with CardContent():
                            P(content["hook"])

                    with Card():
                        with CardHeader():
                            CardTitle("Body Copy")
                        with CardContent():
                            P(content["body"])

                    with Card():
                        with CardHeader():
                            CardTitle("Call to Action")
                        with CardContent():
                            P(content["cta"])
                            with Row(gap=2):
                                Button(
                                    "Use This CTA",
                                    variant="outline",
                                    on_click=SendMessage(f"CTA: {content['cta']}"),
                                )

        with Card():
            with CardFooter():
                with Row(gap=2, align="center"):
                    Button(
                        "Use Full Email",
                        variant="default",
                        on_click=SendMessage(
                            f"Subject: {content['subject']}\n\nHook: {content['hook']}\n\n{content['body']}\n\nCTA: {content['cta']}"
                        ),
                    )
                    with Row(gap=1):
                        for s, label in stages.items():
                            Button(
                                f"Switch to {label}",
                                variant="ghost",
                                size="small",
                                on_click=CallTool(
                                    "generate_email_template",
                                    {"messaging_house_id": str(house.id), "stage": s},
                                ),
                            )

    return PrefabApp(view=view, title=house.name, config=app_config)