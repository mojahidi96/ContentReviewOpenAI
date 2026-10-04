from zipfile import BadZipFile, ZipFile
from io import BytesIO

from app.document_loaders.base import ExtractedDocument, ExtractionError
from app.document_loaders.docx_loader import load_docx
from app.document_loaders.excel_loader import load_xlsx
from app.document_loaders.pdf_loader import load_pdf

ALLOWED_TYPES = {
    ".pdf": ("application/pdf",),
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    ),
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    ),
}


def validate_signature(extension: str, data: bytes) -> None:
    if extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ExtractionError("UNSUPPORTED_FILE", "File signature does not match PDF.")
        return
    try:
        with ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
            required = "word/document.xml" if extension == ".docx" else "xl/workbook.xml"
            if required not in names:
                raise ExtractionError("UNSUPPORTED_FILE", "File signature does not match its extension.")
    except BadZipFile as exc:
        raise ExtractionError("CORRUPT_DOCUMENT", "Office document archive is invalid.") from exc


def extract_document(
    extension: str, data: bytes, max_pages: int
) -> list[ExtractedDocument]:
    if extension == ".pdf":
        return load_pdf(data, max_pages)
    if extension == ".docx":
        return load_docx(data)
    if extension == ".xlsx":
        return load_xlsx(data)
    raise ExtractionError("UNSUPPORTED_FILE", "Only PDF, DOCX, and XLSX files are supported.")
