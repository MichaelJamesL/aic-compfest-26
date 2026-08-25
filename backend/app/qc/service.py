import io
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from ..qc.models import QCBatch, QCImage

#: the classifier's nominal class — an image of a good unit.
NOMINAL = "good"

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
    # "good" is a class the classifier returns, so a populated defect_class is
    # not itself a defect. Counting non-None reported every classified image as
    # defective — and, before anything wrote the column at all, every batch as
    # perfect. Unclassified images are not counted either way.
    defect_count = sum(1 for image in images if image.defect_class not in (None, NOMINAL))
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

def classify_images(images, paths):
    """Label each uploaded image with its defect class, when a classifier exists.

    Takes the QCImage rows rather than re-reading them: the session runs with
    autoflush off, so a query here sees none of the pending inserts and would
    silently label nothing.

    Runs at upload so a batch can report its own defect rate without waiting for
    an analysis. No classifier means the column stays NULL, which reads as
    "not classified" rather than "clean".
    """
    try:
        from src import classify
    except ImportError:
        return
    for image, (name, confidence) in zip(images, classify.classify([str(path) for path in paths])):
        image.defect_class = name
        image.class_confidence = round(confidence, 3)
