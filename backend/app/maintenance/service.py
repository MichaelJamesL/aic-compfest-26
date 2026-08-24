import csv
import io
from pathlib import Path


def rows_from_upload(filename: str, raw: bytes) -> list[dict]:
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if ext == ".xlsx":
        try:
            from openpyxl import load_workbook
            sheet = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).active
            values = list(sheet.values)
        except Exception as exc:
            raise ValueError("invalid_xlsx") from exc
        if not values:
            return []
        headers = [str(value).strip() if value is not None else "" for value in values[0]]
        return [dict(zip(headers, row)) for row in values[1:]]
    raise ValueError("unsupported_import_extension")


def clean_row(row: dict) -> dict:
    return {str(key).strip(): (value.strip() if isinstance(value, str) else value) for key, value in row.items() if key is not None}