import tempfile
from pathlib import Path
from random import gauss, randint

import pytest
from PIL import Image, ImageDraw

from src.schemas import DefectFinding
from src.signals import _severity
from src.vision import _nonzero_region


def test_severity_mapping():
    assert _severity(3.0) == "critical"
    assert _severity(1.6) == "high"
    assert _severity(1.1) == "medium"
    assert _severity(0.0) == "low"


def test_defectfinding_model():
    d = DefectFinding(image="test.png", score=0.95, threshold=0.5, label="defect", severity="high")
    assert d.image == "test.png"
    assert d.score == 0.95
    assert d.method == "patchcore"


def test_nonzero_region():
    import numpy as np

    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[30:60, 20:50] = 1
    x, y, w, h = _nonzero_region(mask)
    assert (x, y, w, h) == (20, 30, 30, 30)


def test_nonzero_region_empty():
    import numpy as np

    mask = np.zeros((100, 100), dtype=np.uint8)
    assert _nonzero_region(mask) == (0, 0, 0, 0)


def test_fit_inspect_round_trip():
    pytest.importorskip("anomalib")
    from src import vision

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        normal_dir = tmp / "normal"
        normal_dir.mkdir()
        for i in range(6):
            img = Image.new("L", (224, 224), 200)
            draw = ImageDraw.Draw(img)
            for _ in range(15):
                x, y = randint(0, 223), randint(0, 223)
                r = randint(1, 3)
                gray = max(0, min(255, int(200 + gauss(0, 8))))
                draw.ellipse([x - r, y - r, x + r, y + r], fill=gray)
            img.save(str(normal_dir / f"plate_{i}.png"))

        vision.fit("test-asset", normal_dir)

        clean_path = str(normal_dir / "plate_0.png")

        defective_path = str(tmp / "defective.png")
        img = Image.new("L", (224, 224), 200)
        draw = ImageDraw.Draw(img)
        for _ in range(15):
            x, y = randint(0, 223), randint(0, 223)
            r = randint(1, 3)
            gray = max(0, min(255, int(200 + gauss(0, 8))))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=gray)
        draw.line([(10, 10), (214, 214)], fill=0, width=4)
        img.save(defective_path)

        findings = vision.inspect("test-asset", [clean_path, defective_path])
        assert len(findings) == 2
        clean_f = findings[0]
        defect_f = findings[1]
        assert clean_f.label == "ok"
        assert defect_f.label == "defect"
        assert defect_f.score > clean_f.score