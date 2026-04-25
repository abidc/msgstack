from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import uvicorn
from src.server import mcp
from src.web_app import app as admin_app

# mcp_app serves at /mcp (default). PathRouter forwards /mcp* without
# stripping the prefix, so mcp_app always sees the full path it expects.
mcp_app = mcp.http_app(
    transport="streamable-http",
    stateless_http=True,
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
    Delegates lifespan to mcp_app so FastMCP's session task group initializes."""

    def __init__(self, mcp, admin):
        self.mcp = mcp
        self.admin = admin

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self.mcp(scope, receive, send)
            return
        if scope["type"] in ("http", "websocket") and scope.get("path", "").startswith("/mcp"):
            await self.mcp(scope, receive, send)
            return
        await self.admin(scope, receive, send)


app = PathRouter(mcp_app, admin_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
