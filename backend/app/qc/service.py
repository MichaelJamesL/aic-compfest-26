import io
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from ..qc.models import QCBatch, QCImage

#: PatchCore's verdict for an image that deviates from the good-unit bank.
DEFECT = "defect"

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
    # NULL means the image was never inspected — no bank for this product —
    # which is not the same as inspected and clean. Counting non-NULL reported
    # every inspected image as defective; counting nothing at all, which is what
    # happened while no code wrote the column, reported every batch as perfect.
    defect_count = sum(1 for image in images if image.defect_class == DEFECT)
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

def inspect_images(images, paths, product):
    """Record PatchCore's verdict per image, when a bank exists for the product.

    The pipeline is detection-only, so `defect_class` holds that verdict —
    "defect" or "ok" — not a defect type. The classifier that would name a type
    is not wired in (see ai-engine/src/classify.py). NULL stays NULL when no
    bank was trained, which reads as "not inspected" rather than "clean".

    Takes the QCImage rows rather than re-reading them: the session runs with
    autoflush off, so a query here sees none of the pending inserts and would
    silently label nothing.
    """
    try:
        from src import vision
    except ImportError:
        return
    findings = vision.inspect(product, [str(path) for path in paths], subject="product")
    for image, finding in zip(images, findings):
        image.defect_class = finding.label
        image.class_confidence = round(finding.score, 3)
