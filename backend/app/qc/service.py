import io
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from ..qc.models import QCBatch, QCImage

QC_EXTENSIONS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def valid_image_bytes(raw: bytes, mime_type: str) -> bool:
    signature = PNG_SIGNATURE if mime_type == "image/png" else b"\xff\xd8\xff"
    if not raw.startswith(signature):
        return False
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def qc_batch_out(db, batch):
    images = list(db.scalars(
        select(QCImage)
        .where(QCImage.batch_id == batch.id)
        .order_by(QCImage.created_at)
    ))
    defect_count = sum(image.defect_class is not None for image in images)
    return {
        "id": batch.id,
        "asset_id": batch.asset_id,
        "factory_id": batch.factory_id,
        "phase": batch.phase,
        "product": batch.product,
        "count": len(images),
        "defect_count": defect_count,
        "defect_rate": defect_count / len(images) if images else 0,
        "images": images,
        "created_at": batch.created_at,
    }