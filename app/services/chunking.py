from dataclasses import dataclass

from app.document_loaders.base import ExtractedDocument


@dataclass
class TextChunk:
    text: str
    metadata: dict


def split_documents(
    documents: list[ExtractedDocument], chunk_size: int, overlap: int
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for document in documents:
        text = document.text.strip()
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start, end)
                if boundary > start + chunk_size // 2:
                    end = boundary
            piece = text[start:end].strip()
            if piece:
                chunks.append(TextChunk(piece, dict(document.metadata)))
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return chunks
