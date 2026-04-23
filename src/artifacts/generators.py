"""Prefab artifact generators for marketing content."""

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
    H3,
    H4,
    If,
    Muted,
    P,
    Row,
    Separator,
    Text,
)
from prefab_ui.components.charts import BarChart, ChartSeries
from prefab_ui.components.control_flow import Else, If as If_
from prefab_ui.rx import Rx
from prefab_ui.rx.mcp import HOST
from prefab_ui.actions.mcp import CallTool, SendMessage

from src.store import Store
from src.models import KeyMessage, SectionType


def _get_store() -> Store:
    store = Store()
    store.init()
    return store


def build_one_pager(house_id: str) -> dict:
    store = _get_store()
    house = store.get_house(UUID(house_id))
    if not house:
        return {"error": f"House {house_id} not found"}
    messages = store.get_key_messages(UUID(house_id))
    personas = store.get_personas(UUID(house_id))

    headline_msgs = [m for m in messages if m.section_type == SectionType.HEADLINE]
    benefit_msgs = [m for m in messages if m.section_type == SectionType.BENEFIT]
    proof_msgs = [m for m in messages if m.section_type == SectionType.PROOF_POINT]

    table_data = [
        {
            "section": m.section_type.value.title(),
            "message": m.content,
            "priority": str(m.priority),
            "channels": ", ".join(c.value for c in m.channels),
        }
        for m in messages[:10]
    ]

    return {
        "type": "one_pager",
        "house_id": house_id,
        "house_name": house.name,
        "components": _one_pager_components(house, personas, headline_msgs, benefit_msgs, proof_msgs, table_data),
    }


def _one_pager_components(house, personas, headlines, benefits, proofs, table_data):
    return Card(
        width="100%",
        children=[
            lambda c: (
                CardHeader(
                    children=[
                        lambda h: (H3(house.name), Muted(house.audience) if house.audience else None),
                    ]
                ),
            )
        ][0],
        children=[
            lambda c: CardContent(
                width="100%",
                children=[
                    lambda cc: (
                        _build_section_block("Positioning", house.positioning),
                        Separator(),
                        _build_section_block("Tagline", house.tagline),
                        Separator(),
                        _build_section_block("Differentiation", house.differentiation),
                        Separator(),
                        _build_key_messages_block(headlines, benefits, proofs),
                        Separator(),
                        _build_personas_block(personas),
                        Separator(),
                        _build_message_table(table_data),
                    )[0],
                ],
            ),
        ][0],
        children=[
            lambda c: CardFooter(
                children=[
                    lambda cf: (
                        Row(
                            gap=2,
                            children=[
                                lambda r: (
                                    Button(
                                        "Use This Messaging",
                                        variant="outline",
                                        on_click=SendMessage(
                                            f"Ground my next piece of content in '{house.name}'"
                                        ),
                                    ),
                                    Button(
                                        "Generate LinkedIn Post",
                                        variant="default",
                                        on_click=CallTool(
                                            "generate_social_posts",
                                            {"messaging_house_id": str(house.id), "channels": ["linkedin"]},
                                        ),
                                    ),
                                )[0],
                            ],
                        ),
                        Muted(f"Last synced: {house.last_synced.strftime('%Y-%m-%d')}" if house.last_synced else "Never synced"),
                    )[0],
                ],
            ),
        ][0],
    )


def _build_section_block(title: str, content: str):
    return Column(gap=2, children=[lambda c: (H4(title), P(content))][0])


def _build_key_messages_block(headlines, benefits, proofs):
    items = []
    for msg in headlines[:2]:
        items.append(lambda i: Badge(msg.content[:80] + ("..." if len(msg.content) > 80 else "")))
    for msg in benefits[:2]:
        items.append(lambda i: Badge(msg.content[:80] + ("..." if len(msg.content) > 80 else "")))
    return Column(gap=2, children=[lambda c: (H4("Key Messages"), Row(gap=1, wrap=True, children=items[:4]))[0]])


def _build_personas_block(personas):
    rows = []
    for p in personas[:2]:
        rows.append(
            lambda r: Card(
                children=[
                    lambda cc: CardHeader(children=[lambda ch: (H4(p.name),)]),
                    lambda cc: CardContent(children=[lambda co: (P(p.description[:150] + ("..." if len(p.description) > 150 else "")),)]),
                ]
            )
        )
    return Column(gap=2, children=[lambda c: (H4("Target Personas"), Row(gap=2, children=rows[:2]))[0]])


def _build_message_table(data):
    return Column(gap=2, children=[lambda c: (H4("Message Inventory"), DataTable(data=data))])


def build_social_posts(house_id: str, channels: list[str] = None) -> dict:
    channels = channels or ["linkedin"]
    store = _get_store()
    house = store.get_house(UUID(house_id))
    if not house:
        return {"error": f"House {house_id} not found"}

    messages = store.get_key_messages(UUID(house_id))
    linkedin_msgs = [m for m in messages if "linkedin" in [c.value for c in m.channels] or m.channels[0].value == "all"]
    linkedin_msgs = linkedin_msgs[:3]

    posts = []
    for i, msg in enumerate(linkedin_msgs):
        posts.append(
            {
                "id": f"post-{i+1}",
                "channel": "LinkedIn",
                "section_type": msg.section_type.value.title(),
                "content": msg.content,
                "variant": msg.variants.get("linkedin", msg.content),
                "priority": msg.priority,
            }
        )

    return {
        "type": "social_posts",
        "house_id": house_id,
        "house_name": house.name,
        "posts": posts,
    }


def build_email_template(house_id: str, stage: str = "awareness") -> dict:
    store = _get_store()
    house = store.get_house(UUID(house_id))
    if not house:
        return {"error": f"House {house_id} not found"}

    messages = store.get_key_messages(UUID(house_id))
    benefit_msgs = [m for m in messages if m.section_type == SectionType.BENEFIT]

    stage_blocks = {
        "awareness": {
            "hook": benefit_msgs[0].content if benefit_msgs else house.positioning,
            "body": f"With Acme, {house.differentiation[:200]}",
            "cta": "See how it works",
        },
        "consideration": {
            "hook": "Already managing cloud infrastructure? Here's what you're missing.",
            "body": f"Teams running on Acme report 60% less time on infra ops. {house.tagline}",
            "cta": "Book a 30-min demo",
        },
        "decision": {
            "hook": "Ready to cut costs without changing your stack?",
            "body": f"We cut cloud costs by 40% for teams like yours. {house.differentiation[:200]}",
            "cta": "Start your free trial",
        },
    }

    block = stage_blocks.get(stage, stage_blocks["awareness"])

    return {
        "type": "email_template",
        "house_id": house_id,
        "house_name": house.name,
        "stage": stage,
        "subject": block["hook"][:60],
        "hook": block["hook"],
        "body": block["body"],
        "cta": block["cta"],
    }