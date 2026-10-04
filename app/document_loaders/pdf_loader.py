import fitz

from app.document_loaders.base import ExtractedDocument, ExtractionError


def load_pdf(data: bytes, max_pages: int) -> list[ExtractedDocument]:
    try:
        with fitz.open(stream=data, filetype="pdf") as pdf:
            if pdf.page_count > max_pages:
                raise ExtractionError("DOCUMENT_TOO_COMPLEX", "PDF exceeds the page limit.")
            pages = []
            for number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if text:
                    pages.append(ExtractedDocument(text=text, metadata={"page_number": number}))
            if not pages:
                raise ExtractionError("OCR_REQUIRED", "PDF contains no extractable text; OCR is required.")
            return pages
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError("CORRUPT_DOCUMENT", "PDF could not be read.") from exc
