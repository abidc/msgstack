"""Abstract base class for document source connectors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RemoteFile:
    file_id: str
    name: str
    mime_type: str
    modified_at: str  # ISO 8601 string from source
    parent_folder_id: Optional[str] = None


class SourceConnector(ABC):
    """Pluggable interface for ingesting documents from external sources."""

    @abstractmethod
    def get_auth_url(self, state: str) -> str:
        """Return the OAuth2 authorization URL for this connector."""

    @abstractmethod
    def exchange_code(self, code: str) -> dict:
        """Exchange an authorization code for tokens. Returns token dict."""

    @abstractmethod
    def refresh_tokens(self, refresh_token: str) -> dict:
        """Refresh an access token. Returns updated token dict."""

    @abstractmethod
    def list_folder(self, folder_id: str, access_token: str) -> list[RemoteFile]:
        """List all supported files in a folder."""

    @abstractmethod
    def export_file(self, file_id: str, mime_type: str, access_token: str) -> bytes:
        """Download or export a file as bytes."""

    @abstractmethod
    def get_initial_page_token(self, access_token: str) -> str:
        """Get the starting pageToken for the Changes API."""

    @abstractmethod
    def poll_changes(
        self, page_token: str, folder_id: str, access_token: str
    ) -> tuple[list[RemoteFile], list[str], str]:
        """Poll for changes since page_token.

        Returns:
            (changed_files, deleted_file_ids, new_page_token)
        """
