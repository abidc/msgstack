"""API key authentication for MsgStack.

When MSGSTACK_AUTH_ENABLED=true all /api/* routes require either:
  X-API-Key: msk_<token>
  Authorization: Bearer msk_<token>

Keys have scopes:
  read  — GET endpoints, search, generate
  write — POST/PATCH/DELETE, upload, extract, seed

When auth is disabled all requests are treated as a superuser with both scopes
belonging to the default workspace.
"""

import hashlib
import secrets
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

from src.config import settings

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_BEARER = HTTPBearer(auto_error=False)

# Scopes
SCOPE_READ = "read"
SCOPE_WRITE = "write"
ALL_SCOPES = {SCOPE_READ, SCOPE_WRITE}


@dataclass
class AuthContext:
    key_id: str
    workspace_id: str
    scopes: set[str]
    name: str = "anonymous"
    is_admin: bool = False


# Sentinel used when auth is disabled
_OPEN_AUTH = AuthContext(
    key_id="__open__",
    workspace_id="default",
    scopes=ALL_SCOPES,
    name="open",
    is_admin=True,
)


def generate_api_key() -> tuple[str, str]:
    """Return (plaintext_key, sha256_hash).  Store only the hash."""
    key = "msk_" + secrets.token_urlsafe(40)
    return key, _hash_key(key)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _extract_raw_key(
    api_key_header: Optional[str],
    bearer: Optional[HTTPAuthorizationCredentials],
) -> Optional[str]:
    if api_key_header:
        return api_key_header
    if bearer and bearer.credentials:
        return bearer.credentials
    return None


async def get_auth_context(
    request: Request,
    api_key_header: Optional[str] = Depends(_API_KEY_HEADER),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(_BEARER),
) -> AuthContext:
    """FastAPI dependency — resolves caller identity.

    Returns _OPEN_AUTH when auth is disabled so callers never need
    to branch on MSGSTACK_AUTH_ENABLED.
    """
    if not settings.auth_enabled:
        return _OPEN_AUTH

    raw_key = _extract_raw_key(api_key_header, bearer)
    if not raw_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide X-API-Key header or Authorization: Bearer <key>.",
        )

    # Import store lazily to avoid circular imports
    from src.store import get_store  # noqa: PLC0415
    store = get_store()
    key_hash = _hash_key(raw_key)
    record = store.get_api_key_by_hash(key_hash)
    if not record or not record["is_active"]:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key.")

    # Update last_used
    store.touch_api_key(record["id"])

    return AuthContext(
        key_id=record["id"],
        workspace_id=record["workspace_id"],
        scopes=set(record["scopes"]),
        name=record["name"],
        is_admin="admin" in record["scopes"],
    )


def require_read(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if SCOPE_READ not in auth.scopes:
        raise HTTPException(403, "This API key does not have read scope.")
    return auth


def require_write(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if SCOPE_WRITE not in auth.scopes:
        raise HTTPException(403, "This API key does not have write scope.")
    return auth
