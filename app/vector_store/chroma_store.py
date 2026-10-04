import logging
from pathlib import Path

import chromadb

from app.errors import VectorStoreUnavailable

logger = logging.getLogger(__name__)


class ChromaStore:
    def __init__(self, path: Path) -> None:
        try:
            self._client = chromadb.PersistentClient(path=str(path))
            self._collection = self._client.get_or_create_collection(
                name="content_review_documents", metadata={"hnsw:space": "cosine"}
            )
        except Exception as exc:
            logger.exception("Unable to initialize local vector store")
            raise VectorStoreUnavailable() from exc

    def add_chunks(
        self, ids: list[str], texts: list[str], embeddings: list[list[float]], metadatas: list[dict]
    ) -> None:
        try:
            self._collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        except Exception as exc:
            logger.exception("Vector store failed to index document chunks")
            raise VectorStoreUnavailable() from exc

    def query(
        self, embedding: list[float], document_ids: list[str], tenant_id: str, limit: int
    ) -> list[dict]:
        try:
            doc_filter: dict = {"document_id": document_ids[0]} if len(document_ids) == 1 else {
                "document_id": {"$in": document_ids}
            }
            where = {"$and": [{"tenant_id": tenant_id}, doc_filter]}
            result = self._collection.query(
                query_embeddings=[embedding],
                n_results=limit,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            records = []
            for index, text in enumerate(result["documents"][0]):
                records.append(
                    {
                        "chunk_id": result["ids"][0][index],
                        "text": text,
                        "metadata": result["metadatas"][0][index],
                        "distance": result["distances"][0][index],
                    }
                )
            return records
        except Exception as exc:
            logger.exception("Vector store retrieval failed")
            raise VectorStoreUnavailable() from exc

    def delete_document(self, document_id: str, tenant_id: str) -> None:
        try:
            self._collection.delete(where={"$and": [{"document_id": document_id}, {"tenant_id": tenant_id}]})
        except Exception as exc:
            logger.exception("Vector store deletion failed")
            raise VectorStoreUnavailable() from exc
