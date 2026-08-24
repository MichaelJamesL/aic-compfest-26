import io
import re
from pathlib import Path

from fastapi import UploadFile

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
MAX_PDF_PAGES = 200
MAX_PDF_TEXT = 2_000_000
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}
DOCUMENT_KINDS = {"sop", "manual", "log", "qc_standard", "maintenance_history"}


def factory_storage_key(factory_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", factory_id):
        raise ValueError("invalid_factory_id")
    return factory_id


def safe_storage_path(settings, key: str) -> Path:
    root = settings.storage_path.resolve()
    path = (root / key).resolve()
    if root not in path.parents:
        raise ValueError("invalid_storage_key")
    return path


def extract_text(filename: str, content_type: str | None, raw: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw), strict=False)
            if len(reader.pages) > MAX_PDF_PAGES:
                raise ValueError("pdf_too_many_pages")
            parts, total = [], 0
            for page in reader.pages:
                part = page.extract_text() or ""
                total += len(part)
                if total > MAX_PDF_TEXT:
                    raise ValueError("pdf_text_too_large")
                parts.append(part)
            return "\n".join(parts).strip()
        except Exception as exc:
            if str(exc) in {"pdf_too_many_pages", "pdf_text_too_large"}:
                raise
            raise ValueError("invalid_pdf") from exc
    if (content_type or "").startswith("text/") or ext in {".txt", ".md", ".csv", ".json"}:
        return raw.decode("utf-8", errors="replace")
    return ""


def check_file(file: UploadFile, max_size: int = MAX_UPLOAD_SIZE, allowed_extensions=None) -> None:
    if not file.filename:
        raise ValueError("empty_filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in (allowed_extensions or ALLOWED_EXTENSIONS):
        raise ValueError(f"unsupported_extension:{ext}")
    preview = file.file.read(max_size + 1)
    file.file.seek(0)
    if len(preview) > max_size:
        raise ValueError("file_too_large")
    binary_allowed = allowed_extensions or {".csv", ".json", ".pdf"}
    if not (file.content_type or "").startswith("text/") and ext not in binary_allowed:
        try:
            preview.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("non_text_file")