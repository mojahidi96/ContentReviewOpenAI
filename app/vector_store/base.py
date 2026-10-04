from typing import Protocol


class VectorStore(Protocol):
    def add_chunks(
        self, ids: list[str], texts: list[str], embeddings: list[list[float]], metadatas: list[dict]
    ) -> None: ...

    def query(
        self,
        embedding: list[float],
        document_ids: list[str],
        tenant_id: str,
        limit: int,
    ) -> list[dict]: ...

    def delete_document(self, document_id: str, tenant_id: str) -> None: ...
