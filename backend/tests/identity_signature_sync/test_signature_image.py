from datetime import datetime, timezone
from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from app.services.signature_image import (
    SignatureImageError,
    normalize_signature_image,
)
from app.services.identity_time import is_after_modified_watermark


def _png(width: int, height: int, *, transparent: bool = False) -> bytes:
    mode = "RGBA" if transparent else "RGB"
    background = (255, 255, 255, 0) if transparent else "white"
    image = Image.new(mode, (width, height), background)
    draw = ImageDraw.Draw(image)
    draw.line((5, height // 2, width - 5, height // 2), fill="black", width=3)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _open(data: bytes) -> Image.Image:
    image = Image.open(BytesIO(data))
    image.load()
    return image


def test_signature_is_resized_to_150_with_proportional_height():
    normalized = normalize_signature_image(_png(542, 195))
    image = _open(normalized)
    assert image.format == "JPEG"
    assert image.size == (150, 54)


def test_signature_smaller_than_limit_is_not_enlarged():
    normalized = normalize_signature_image(_png(100, 40))
    assert _open(normalized).size == (100, 40)


def test_transparent_signature_uses_white_jpeg_background():
    normalized = normalize_signature_image(_png(200, 80, transparent=True))
    image = _open(normalized)
    assert image.mode == "RGB"
    assert image.size == (150, 60)
    assert min(image.getpixel((0, 0))) >= 250


def test_invalid_signature_fails_closed():
    with pytest.raises(SignatureImageError, match="signature_image_invalid"):
        normalize_signature_image(b"not-an-image")


def test_empty_and_zero_width_fail_closed():
    with pytest.raises(SignatureImageError, match="signature_image_invalid"):
        normalize_signature_image(b"")
    with pytest.raises(SignatureImageError):
        normalize_signature_image(_png(10, 10), max_width=0)


def test_naive_source_timestamp_can_compare_with_aware_watermark():
    parsed = datetime(2026, 8, 10, 2, 0)
    watermark = datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc)
    assert is_after_modified_watermark(parsed, watermark, "B", "A")


def test_equal_timestamp_uses_stable_tie_breaker_after_timezone_normalization():
    parsed = datetime(2026, 8, 10, 2, 0)
    watermark = datetime(2026, 8, 10, 2, 0, tzinfo=timezone.utc)
    assert is_after_modified_watermark(parsed, watermark, "B", "A")
    assert not is_after_modified_watermark(parsed, watermark, "A", "A")
