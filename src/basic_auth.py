import base64
import logging

log = logging.getLogger(__name__)


class BasicAuthMiddleware:
    def __init__(self, app, username: str, password: str, enabled: bool = True, realm: str = "MsgStack"):
        self.app = app
        self.username = username
        self.password = password
        self.enabled = enabled
        self.realm = realm

    async def __call__(self, scope, receive, send):
        if not self.enabled or scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        auth_header = ""
        for name, value in scope.get("headers", []):
            if name == b"authorization":
                auth_header = value.decode("latin-1")
                break

        if not auth_header.startswith("Basic "):
            await self._unauthorized(send)
            return

        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            user, _, passwd = decoded.partition(":")
            if user != self.username or passwd != self.password:
                raise ValueError("Invalid credentials")
        except Exception:
            await self._unauthorized(send)
            return

        await self.app(scope, receive, send)

    async def _unauthorized(self, send):
        body = b"Unauthorized"
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"text/plain"),
                (b"content-length", str(len(body)).encode()),
                (b"www-authenticate", f'Basic realm="{self.realm}"'.encode()),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
