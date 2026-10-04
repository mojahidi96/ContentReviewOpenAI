import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.document import DocumentRecord


class DocumentRepository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    document_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    error_code TEXT,
                    created_at TEXT NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def create(self, document_id: str, tenant_id: str, name: str, media_type: str, size: int) -> DocumentRecord:
        created = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO documents
                   (document_id, tenant_id, document_name, status, media_type, size_bytes, created_at)
                   VALUES (?, ?, ?, 'uploaded', ?, ?, ?)""",
                (document_id, tenant_id, name, media_type, size, created),
            )
        return DocumentRecord(
            documentId=document_id, tenantId=tenant_id, documentName=name, status="uploaded",
            mediaType=media_type, sizeBytes=size, createdAt=created,
        )

    def update_status(
        self, document_id: str, tenant_id: str, status: str, chunk_count: int = 0, error_code: str | None = None
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE documents SET status = ?, chunk_count = ?, error_code = ?
                   WHERE document_id = ? AND tenant_id = ?""",
                (status, chunk_count, error_code, document_id, tenant_id),
            )

    def get(self, document_id: str, tenant_id: str) -> DocumentRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE document_id = ? AND tenant_id = ?",
                (document_id, tenant_id),
            ).fetchone()
        return DocumentRecord(
            documentId=row["document_id"], tenantId=row["tenant_id"], documentName=row["document_name"],
            status=row["status"], mediaType=row["media_type"], sizeBytes=row["size_bytes"],
            chunkCount=row["chunk_count"], errorCode=row["error_code"], createdAt=row["created_at"],
        ) if row else None

    def delete(self, document_id: str, tenant_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM documents WHERE document_id = ? AND tenant_id = ?",
                (document_id, tenant_id),
            )
            return cursor.rowcount > 0
