"""MsgStack MCP Server entry point."""

import os
from typing import Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

from src.grounding import tools as grounding_tools
from src.grounding.session import reset_session
from src.store import Store

load_dotenv()

mcp = FastMCP("MsgStack", dependencies=["fastmcp[apps]"])


@mcp.tool()
def search_messaging(
    query: str,
    section_types: Optional[list[str]] = None,
    personas: Optional[list[str]] = None,
    channels: Optional[list[str]] = None,
    message_houses: Optional[list[str]] = None,
    include_variants: bool = True,
    min_priority: Optional[int] = None,
) -> dict:
    """Search marketing messaging frameworks for grounding content.

    Provide a natural language query and optional filters to retrieve relevant
    messaging chunks from your brand's messaging libraries. Use this before
    generating any marketing content to ensure it aligns with approved messaging.

    Args:
        query: What messaging content are you looking for? Include section types,
               personas, and channels naturally (e.g., "headlines for CTOs on LinkedIn").
        section_types: Filter by message type: headline, subhead, benefit, proof_point,
                      objection, social_proof, positioning.
        personas: Filter by specific audience personas (e.g., SMB CTO, FinOps Manager).
        channels: Filter by channel: linkedin, email, landing, paid, twitter, blog.
        message_houses: Restrict to specific message houses by ID.
        include_variants: Include channel-specific message variants in results.
        min_priority: Only return messages at or above this priority (1=highest).

    Returns:
        Matched messaging chunks with confidence scores and grounding context.
    """
    return grounding_tools.search_messaging(
        query=query,
        section_types=section_types,
        personas=personas,
        channels=channels,
        message_houses=message_houses,
        include_variants=include_variants,
        min_priority=min_priority,
    ).model_dump()


@mcp.tool()
def set_active_house(house_id: str) -> dict:
    """Pin a message house as the active grounding context for the session.

    Subsequent searches will default to this house unless overridden.
    Call this first when you know which messaging framework to use.
    """
    return grounding_tools.set_active_house(house_id)


@mcp.tool()
def get_message_house(
    house_id: Optional[str] = None,
    house_name: Optional[str] = None,
    include: Optional[list[str]] = None,
) -> dict:
    """Retrieve a full message house with all key messages and personas.

    Args:
        house_id: UUID of the message house.
        house_name: Name of the message house (alternative to house_id).
        include: Sections to include: 'key_messages', 'personas', 'positioning', 'all'.
    """
    return grounding_tools.get_message_house(house_id, house_name, include)


@mcp.tool()
def list_message_houses(query: Optional[str] = None) -> dict:
    """List all available messaging frameworks.

    Args:
        query: Optional text search across house names and summaries.
    """
    return grounding_tools.list_message_houses(query)


@mcp.tool()
def compare_houses(house_ids: list[str]) -> dict:
    """Compare two or more message houses side by side.

    Useful for cross-quarter positioning changes or multi-brand scenarios.
    """
    return grounding_tools.compare_houses(house_ids)


@mcp.tool()
def get_grounding_context() -> dict:
    """Get the current grounding context for this session.

    Returns which house is active, which personas are in scope, and which
    chunks have been used so far.
    """
    return grounding_tools.get_grounding_context().model_dump()


@mcp.tool()
def generate_one_pager(messaging_house_id: str, app: bool = True) -> dict:
    """Generate a messaging one-pager from a message house.

    Returns a structured display of the house's positioning, key messages,
    personas, and message inventory — rendered as a Prefab UI in chat.

    Args:
        messaging_house_id: UUID of the message house.
        app: Set to True to render as an interactive Prefab UI.
    """
    from src.artifacts.generators import build_one_pager
    result = build_one_pager(messaging_house_id)
    if "error" in result:
        return result
    return {"prefab": result, "raw": result}


@mcp.tool()
def generate_social_posts(
    messaging_house_id: str,
    channels: Optional[list[str]] = None,
    count: int = 3,
    app: bool = True,
) -> dict:
    """Generate social media posts grounded in the message house.

    Args:
        messaging_house_id: UUID of the message house.
        channels: Which social channels (linkedin, twitter, etc.).
        count: Number of posts to generate per channel.
        app: Set to True to render as an interactive Prefab UI.
    """
    from src.artifacts.generators import build_social_posts
    result = build_social_posts(messaging_house_id, channels)
    if "error" in result:
        return result
    return {"prefab": result, "raw": result}


@mcp.tool()
def generate_email_template(
    messaging_house_id: str,
    stage: str = "awareness",
    app: bool = True,
) -> dict:
    """Generate an email template grounded in the message house.

    Args:
        messaging_house_id: UUID of the message house.
        stage: Funnel stage: awareness, consideration, or decision.
        app: Set to True to render as an interactive Prefab UI.
    """
    from src.artifacts.generators import build_email_template
    result = build_email_template(messaging_house_id, stage)
    if "error" in result:
        return result
    return {"prefab": result, "raw": result}


@mcp.tool()
def reset_conversation() -> dict:
    """Reset the grounding session context.

    Clears the active house, recent searches, and used chunks.
    Use when starting a new topic or switching message houses.
    """
    reset_session()
    return {"message": "Session reset. No active message house."}


@mcp.tool()
def seed_database() -> dict:
    """Seed the database with sample messaging content.

    Loads a realistic B2B SaaS messaging house for testing.
    """
    from seed_data.seed import seed as run_seed
    run_seed()
    return {"message": "Database seeded with sample messaging content."}


def main():
    store = Store()
    store.init()
    mcp.run()


if __name__ == "__main__":
    main()