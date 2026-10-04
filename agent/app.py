"""Entrypoint for the agent service — mounts the Slack and Teams ASGI apps
behind one uvicorn process, mirroring run_server.py's PathRouter pattern in
the main msgstack-mcp service rather than inventing a different convention.
"""

import logging

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from agent.config import settings
from agent.slack_app import asgi_app as slack_asgi_app
from agent.teams_app import asgi_app as teams_asgi_app

logging.basicConfig(level=logging.INFO)


async def _health(request):
    return JSONResponse({"ok": True})


# Routes already live at distinct, non-overlapping paths (/slack/events,
# /teams/messages) — concatenate rather than Mount() to avoid a shared ""
# prefix ambiguity between the two sub-apps.
app = Starlette(routes=[
    Route("/healthz", _health),
    *slack_asgi_app.routes,
    *teams_asgi_app.routes,
])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
