from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import uvicorn
from src.server import mcp
from src.web_app import app as admin_app
from src.basic_auth import BasicAuthMiddleware
from src.config import settings

# mcp_app serves at /mcp (default). PathRouter forwards /mcp* without
# stripping the prefix, so mcp_app always sees the full path it expects.
mcp_app = mcp.http_app(
    transport="streamable-http",
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
            allow_headers=["*"],
            expose_headers=["mcp-session-id"],
            allow_credentials=True,
        )
    ]
)


class PathRouter:
    """Route /mcp* to mcp_app (full path, no stripping), everything else to admin_app.
    Delegates lifespan to mcp_app so FastMCP's session task group initializes.
    Also starts the admin app's sync engine background loop on startup."""

    def __init__(self, mcp, admin):
        self.mcp = mcp
        self.admin = admin

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            # Intercept startup to boot sync engine, seed default templates, and rebuild graph
            async def patched_receive():
                msg = await receive()
                if msg["type"] == "lifespan.startup":
                    try:
                        from src.web_app import _sync_engine
                        _sync_engine.start()
                    except Exception:
                        pass
                    try:
                        from src.design.template_registry import seed_default_templates
                        seed_default_templates()
                    except Exception:
                        pass
                    try:
                        from src.grounding.graph import get_graph_engine
                        get_graph_engine().rebuild()
                    except Exception:
                        pass
                return msg
            await self.mcp(scope, patched_receive, send)
            return
        if scope["type"] in ("http", "websocket") and scope.get("path", "").startswith("/mcp"):
            await self.mcp(scope, receive, send)
            return
        await self.admin(scope, receive, send)


_app = PathRouter(mcp_app, admin_app)

app = BasicAuthMiddleware(
    _app,
    username=settings.basic_auth_user,
    password=settings.basic_auth_pass,
    enabled=settings.basic_auth_enabled,
    realm="mcp.abidc.dev",
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
