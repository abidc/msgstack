"""Background sync engine — polls connected sources and ingests changed files."""

import asyncio
import logging
import os
from datetime import datetime, timezone

from src.sources.base import RemoteFile
from src.sources.google_drive import GoogleDriveConnector

log = logging.getLogger(__name__)

_POLL_INTERVAL = int(os.environ.get("GDRIVE_POLL_INTERVAL", "300"))  # 5 min default


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SyncEngine:
    def __init__(self, store, data_dir: str = "data"):
        self.store = store
        self.data_dir = data_dir
        self._task: asyncio.Task | None = None

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
            log.info("Source sync loop started (interval=%ds)", _POLL_INTERVAL)

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            log.info("Source sync loop stopped")

    async def _loop(self):
        while True:
            try:
                await self.sync_all()
            except Exception as exc:
                log.error("Sync loop error: %s", exc, exc_info=True)
            await asyncio.sleep(_POLL_INTERVAL)

    async def sync_all(self):
        connections = self.store.list_connections()
        for conn in connections:
            if conn.get("status") in ("disconnected",):
                continue
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.sync_connection, conn["id"]
                )
            except Exception as exc:
                log.error("Failed syncing connection %s: %s", conn["id"], exc)

    def sync_connection(self, connection_id: str):
        conn = self.store.get_connection(connection_id)
        if not conn:
            return

        connector = GoogleDriveConnector()

        # Refresh access token if needed
        try:
            token_data = connector.refresh_tokens(conn["refresh_token"])
            access_token = token_data["access_token"]
            self.store.update_connection(connection_id, {"access_token": access_token})
        except Exception as exc:
            log.error("Token refresh failed for %s: %s", connection_id, exc)
            self.store.update_connection(connection_id, {"status": "error", "error_message": str(exc)})
            return

        self.store.update_connection(connection_id, {"status": "syncing"})

        # Heal folder_name if it was stored as a raw ID
        if conn.get("folder_name") == conn.get("folder_id"):
            try:
                name = connector.get_folder_name(conn["folder_id"], access_token)
                if name != conn["folder_id"]:
                    self.store.update_connection(connection_id, {"folder_name": name})
            except Exception:
                pass

        try:
            changed, deleted_ids, new_page_token = connector.poll_changes(
                page_token=conn["page_token"],
                folder_id=conn["folder_id"],
                access_token=access_token,
            )

            for file_info in changed:
                self._ingest_file(conn, file_info, access_token)

            # Heal source files whose spec was deleted externally (e.g. via the UI or a
            # previous orphan cleanup). Re-queue them so the error retry loop below re-ingests.
            from src.store import get_store as _get_store
            _live_store = _get_store()
            for _sf in self.store.list_source_files(connection_id):
                if _sf.get("sync_status") == "synced" and _sf.get("spec_id"):
                    try:
                        _spec = _live_store.get_spec(_sf["spec_id"])
                    except Exception:
                        _spec = None
                    if not _spec:
                        log.info(
                            "Spec %s missing for source file %s — re-queuing for re-ingest",
                            _sf["spec_id"], _sf["file_name"],
                        )
                        self.store.upsert_source_file(
                            connection_id=connection_id,
                            drive_file_id=_sf["drive_file_id"],
                            file_name=_sf["file_name"],
                            mime_type=_sf["mime_type"],
                            drive_modified_at=_sf.get("drive_modified_at", ""),
                            sync_status="error",
                            error_message="spec missing, re-queued for re-ingest",
                        )

            # Retry any files still in error state (e.g. from a previous failed attempt)
            error_files = [f for f in self.store.list_source_files(connection_id) if f.get("sync_status") == "error"]
            changed_ids = {f.file_id for f in changed}
            for ef in error_files:
                if ef["drive_file_id"] not in changed_ids:
                    try:
                        rf = RemoteFile(
                            file_id=ef["drive_file_id"],
                            name=ef["file_name"],
                            mime_type=ef["mime_type"],
                            modified_at=ef.get("drive_modified_at", ""),
                        )
                        self._ingest_file(conn, rf, access_token)
                    except Exception as exc:
                        log.warning("Retry ingest failed for %s: %s", ef["file_name"], exc)

            for drive_file_id in deleted_ids:
                sf = self.store.get_source_file_by_drive_id(connection_id, drive_file_id)
                if sf and sf.get("spec_id"):
                    try:
                        from src.store import get_store
                        get_store().delete_spec(sf["spec_id"])
                    except Exception:
                        pass
                self.store.delete_source_file(connection_id, drive_file_id)

            self.store.update_connection(connection_id, {
                "page_token": new_page_token,
                "status": "connected",
                "last_sync_at": _now(),
                "error_message": "",
            })
            log.info("Synced connection %s: %d changed, %d deleted", connection_id, len(changed), len(deleted_ids))

        except Exception as exc:
            log.error("Sync failed for connection %s: %s", connection_id, exc, exc_info=True)
            self.store.update_connection(connection_id, {"status": "error", "error_message": str(exc)})

    def _ingest_file(self, conn: dict, file_info: RemoteFile, access_token: str):
        import tempfile
        from pathlib import Path
        from src.pipeline.extract import extract_text
        from src.pipeline.structure import SpecStructurer, detect_document_type
        from src.models import Spec, SpecStatus, SchemaType
        from src.store import get_store

        store = get_store()
        connector = GoogleDriveConnector()

        try:
            raw_bytes = connector.export_file(file_info.file_id, file_info.mime_type, access_token)
        except Exception as exc:
            log.error("Export failed for %s (%s): %s", file_info.name, file_info.file_id, exc)
            self.store.upsert_source_file(
                connection_id=conn["id"],
                drive_file_id=file_info.file_id,
                file_name=file_info.name,
                mime_type=file_info.mime_type,
                drive_modified_at=file_info.modified_at,
                sync_status="error",
                error_message=str(exc),
            )
            return

        # Determine file extension so extract_text can infer the type
        from src.sources.google_drive import _EXPORT_MAP
        _NATIVE_DOCX_MIMES = {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }
        if file_info.mime_type in _EXPORT_MAP:
            ext = ".docx"
        elif file_info.mime_type in _NATIVE_DOCX_MIMES:
            ext = ".docx"
        elif file_info.mime_type == "application/pdf":
            ext = ".pdf"
        else:
            ext = ".txt"

        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(raw_bytes)
                tmp_path = Path(tmp.name)
            raw_text = extract_text(tmp_path)
            tmp_path.unlink(missing_ok=True)
        except Exception as exc:
            log.error("Text extraction failed for %s: %s", file_info.name, exc)
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            self.store.upsert_source_file(
                connection_id=conn["id"],
                drive_file_id=file_info.file_id,
                file_name=file_info.name,
                mime_type=file_info.mime_type,
                drive_modified_at=file_info.modified_at,
                sync_status="error",
                error_message=f"extraction: {exc}",
            )
            return

        doc_type = detect_document_type(raw_text, file_info.name)
        structurer = SpecStructurer()
        try:
            structured, _usage = structurer.structure(raw_text, source_name=file_info.name, document_type=doc_type)
        except Exception as exc:
            log.error("Structuring failed for %s: %s", file_info.name, exc)
            self.store.upsert_source_file(
                connection_id=conn["id"],
                drive_file_id=file_info.file_id,
                file_name=file_info.name,
                mime_type=file_info.mime_type,
                drive_modified_at=file_info.modified_at,
                sync_status="error",
                error_message=f"structure: {exc}",
            )
            return

        # Delete all specs previously created for this Drive file (including orphans
        # from failed retries that were never linked back to the source_file record).
        store.delete_specs_by_source_id(file_info.file_id)

        # Commit to DB + Turbovec + graph
        from src.web_app import _commit_structured_spec
        try:
            spec, indexed, _ = _commit_structured_spec(
                structured,
                filename=file_info.file_id,
                document_type=doc_type,
                raw_markdown=raw_text,
            )
            spec.source = "google_drive"
            spec.source_id = file_info.file_id
            store.upsert_spec(spec)
        except Exception as exc:
            log.error("Commit failed for %s: %s", file_info.name, exc, exc_info=True)
            self.store.upsert_source_file(
                connection_id=conn["id"],
                drive_file_id=file_info.file_id,
                file_name=file_info.name,
                mime_type=file_info.mime_type,
                drive_modified_at=file_info.modified_at,
                sync_status="error",
                error_message=f"commit: {exc}",
            )
            return

        self.store.upsert_source_file(
            connection_id=conn["id"],
            drive_file_id=file_info.file_id,
            file_name=file_info.name,
            mime_type=file_info.mime_type,
            drive_modified_at=file_info.modified_at,
            spec_id=str(spec.id),
            sync_status="synced",
            error_message="",
        )

        # Rebuild graph so MCP tools see the newly ingested spec immediately
        try:
            from src.grounding.graph import get_graph_engine
            get_graph_engine().rebuild()
        except Exception as exc:
            log.warning("Graph rebuild after sync skipped: %s", exc)

        log.info("Ingested %s → spec %s (indexed=%s)", file_info.name, spec.id, indexed)

    def initial_sync(self, connection_id: str):
        """Full folder scan for a newly-connected source. Called once after OAuth."""
        conn = self.store.get_connection(connection_id)
        if not conn:
            return

        connector = GoogleDriveConnector()
        try:
            token_data = connector.refresh_tokens(conn["refresh_token"])
            access_token = token_data["access_token"]
            self.store.update_connection(connection_id, {"access_token": access_token})
        except Exception:
            access_token = conn["access_token"]

        self.store.update_connection(connection_id, {"status": "syncing"})
        try:
            files = connector.list_folder(conn["folder_id"], access_token)
            for file_info in files:
                self._ingest_file(conn, file_info, access_token)
            page_token = connector.get_initial_page_token(access_token)
            self.store.update_connection(connection_id, {
                "page_token": page_token,
                "status": "connected",
                "last_sync_at": _now(),
                "error_message": "",
            })
            log.info("Initial sync for %s: %d files ingested", connection_id, len(files))
        except Exception as exc:
            log.error("Initial sync failed for %s: %s", connection_id, exc, exc_info=True)
            self.store.update_connection(connection_id, {"status": "error", "error_message": str(exc)})


_engine: SyncEngine | None = None


def get_sync_engine() -> SyncEngine:
    global _engine
    if _engine is None:
        raise RuntimeError("SyncEngine not initialized")
    return _engine


def init_sync_engine(store, data_dir: str = "data") -> SyncEngine:
    global _engine
    _engine = SyncEngine(store, data_dir)
    return _engine
