"""Environment-driven config for the agent service. Mirrors src/config.py's
pattern (plain env lookups with sane dev defaults) rather than importing it,
to keep this package decoupled from src/.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSettings:
    # MsgStack MCP server this agent connects to as a client.
    msgstack_mcp_url: str = os.environ.get("MSGSTACK_MCP_URL", "http://msgstack-mcp:8001/mcp")
    msgstack_base_url: str = os.environ.get("MSGSTACK_BASE_URL", "http://msgstack-mcp:8001")
    msgstack_basic_user: str = os.environ.get("MSGSTACK_BASIC_USER", "")
    msgstack_basic_pass: str = os.environ.get("MSGSTACK_BASIC_PASS", "")

    # Slack (Events API, Bolt for Python).
    slack_bot_token: str = os.environ.get("SLACK_BOT_TOKEN", "")
    slack_signing_secret: str = os.environ.get("SLACK_SIGNING_SECRET", "")

    # Teams (Bot Framework SDK — see agent/teams_app.py for why not the JS/.NET-first Teams AI Library).
    teams_app_id: str = os.environ.get("TEAMS_APP_ID", "")
    teams_app_password: str = os.environ.get("TEAMS_APP_PASSWORD", "")

    # Identity-mapping store (separate small sqlite db, not the main msgstack.db).
    agent_identity_db_url: str = os.environ.get(
        "AGENT_IDENTITY_DB_URL", "sqlite:///data/agent_identity.db"
    )

    port: int = int(os.environ.get("AGENT_PORT", "8010"))


settings = AgentSettings()
