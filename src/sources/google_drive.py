"""Google Drive source connector — OAuth2 + folder watch via Changes API."""

import io
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

import requests

from src.sources.base import RemoteFile, SourceConnector

log = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_DRIVE_API = "https://www.googleapis.com/drive/v3"

# MIME types we can ingest
SUPPORTED_MIME_TYPES = {
    # Google Docs → exported as DOCX
    "application/vnd.google-apps.document",
    # DOCX
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # PDF
    "application/pdf",
    # Plain text and Markdown
    "text/plain",
    "text/markdown",
}

# Export MIME types for Google Workspace formats
_EXPORT_MAP = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
}


def _folder_id_from_url(folder_id_or_url: str) -> str:
    """Accept either a plain folder ID or a Drive URL and return the folder ID."""
    if folder_id_or_url.startswith("http"):
        # https://drive.google.com/drive/folders/<id>
        m = re.search(r"/folders/([a-zA-Z0-9_-]+)", folder_id_or_url)
        if m:
            return m.group(1)
    return folder_id_or_url.strip()


class GoogleDriveConnector(SourceConnector):
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ):
        self.client_id = client_id or os.environ.get("GOOGLE_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("GOOGLE_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or _default_redirect_uri()

    def get_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
        return f"{_AUTH_URL}?{query}"

    def exchange_code(self, code: str) -> dict:
        resp = requests.post(
            _TOKEN_URL,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_in": data.get("expires_in", 3600),
        }

    def refresh_tokens(self, refresh_token: str) -> dict:
        resp = requests.post(
            _TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data["access_token"],
            "expires_in": data.get("expires_in", 3600),
        }

    def _headers(self, access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    def get_account_email(self, access_token: str) -> str:
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers=self._headers(access_token),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("email", "")

    def get_folder_name(self, folder_id: str, access_token: str) -> str:
        resp = requests.get(
            f"{_DRIVE_API}/files/{folder_id}",
            params={"fields": "name", "supportsAllDrives": "true"},
            headers=self._headers(access_token),
            timeout=10,
        )
        if resp.status_code != 200:
            return folder_id
        return resp.json().get("name", folder_id)

    def list_folder(self, folder_id: str, access_token: str) -> list[RemoteFile]:
        folder_id = _folder_id_from_url(folder_id)
        files: list[RemoteFile] = []
        page_token: Optional[str] = None
        mime_filter = " or ".join(
            f"mimeType='{m}'" for m in SUPPORTED_MIME_TYPES
        )
        query = f"'{folder_id}' in parents and trashed=false and ({mime_filter})"
        while True:
            params: dict = {
                "q": query,
                "fields": "nextPageToken,files(id,name,mimeType,modifiedTime)",
                "pageSize": 100,
            }
            if page_token:
                params["pageToken"] = page_token
            resp = requests.get(
                f"{_DRIVE_API}/files",
                params=params,
                headers=self._headers(access_token),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for f in data.get("files", []):
                files.append(
                    RemoteFile(
                        file_id=f["id"],
                        name=f["name"],
                        mime_type=f["mimeType"],
                        modified_at=f.get("modifiedTime", ""),
                        parent_folder_id=folder_id,
                    )
                )
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return files

    def export_file(self, file_id: str, mime_type: str, access_token: str) -> bytes:
        export_mime = _EXPORT_MAP.get(mime_type)
        if export_mime:
            resp = requests.get(
                f"{_DRIVE_API}/files/{file_id}/export",
                params={"mimeType": export_mime},
                headers=self._headers(access_token),
                timeout=60,
            )
        else:
            resp = requests.get(
                f"{_DRIVE_API}/files/{file_id}",
                params={"alt": "media"},
                headers=self._headers(access_token),
                timeout=60,
            )
        resp.raise_for_status()
        return resp.content

    def get_initial_page_token(self, access_token: str) -> str:
        resp = requests.get(
            f"{_DRIVE_API}/changes/startPageToken",
            headers=self._headers(access_token),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["startPageToken"]

    def poll_changes(
        self, page_token: str, folder_id: str, access_token: str
    ) -> tuple[list[RemoteFile], list[str], str]:
        folder_id = _folder_id_from_url(folder_id)
        changed: list[RemoteFile] = []
        deleted_ids: list[str] = []
        current_token = page_token

        while True:
            resp = requests.get(
                f"{_DRIVE_API}/changes",
                params={
                    "pageToken": current_token,
                    "fields": (
                        "nextPageToken,newStartPageToken,"
                        "changes(fileId,removed,file(id,name,mimeType,modifiedTime,parents,trashed))"
                    ),
                    "includeRemoved": "true",
                    "spaces": "drive",
                },
                headers=self._headers(access_token),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            for change in data.get("changes", []):
                file_id = change.get("fileId", "")
                if change.get("removed"):
                    deleted_ids.append(file_id)
                    continue
                f = change.get("file", {})
                if f.get("trashed"):
                    deleted_ids.append(file_id)
                    continue
                # Only include files in our watched folder
                parents = f.get("parents", [])
                if folder_id not in parents:
                    continue
                mime = f.get("mimeType", "")
                if mime not in SUPPORTED_MIME_TYPES:
                    continue
                changed.append(
                    RemoteFile(
                        file_id=f["id"],
                        name=f["name"],
                        mime_type=mime,
                        modified_at=f.get("modifiedTime", ""),
                        parent_folder_id=folder_id,
                    )
                )

            current_token = data.get("nextPageToken") or data.get("newStartPageToken", current_token)
            if "nextPageToken" not in data:
                break

        return changed, deleted_ids, current_token


def _default_redirect_uri() -> str:
    base = os.environ.get("MSGSTACK_BASE_URL", "http://localhost:8001")
    return f"{base}/api/connections/google-drive/callback"
