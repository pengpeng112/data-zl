"""Pure, fail-closed image normalization for JHEMR signatures."""

from __future__ import annotations

import io

from PIL import Image, UnidentifiedImageError

SIGNATURE_MAX_WIDTH = 150
SIGNATURE_MAX_PIXELS = 20_000_000
SIGNATURE_JPEG_QUALITY = 90


class SignatureImageError(ValueError):
    """Raised when a source signature cannot be safely normalized."""


def normalize_signature_image(image: bytes, *, max_width: int = SIGNATURE_MAX_WIDTH) -> bytes:
    """Return a JPEG signature no wider than ``max_width`` pixels."""
    if not image or max_width < 1:
        raise SignatureImageError("signature_image_invalid")
    try:
        with Image.open(io.BytesIO(image)) as source:
            width, height = source.size
            if width < 1 or height < 1 or width * height > SIGNATURE_MAX_PIXELS:
                raise SignatureImageError("signature_image_dimensions_invalid")
            source.load()
            if width > max_width:
                target_height = max(1, round(height * max_width / width))
                source = source.resize(
                    (max_width, target_height),
                    Image.Resampling.LANCZOS,
                )
            if source.mode in {"RGBA", "LA"} or (
                source.mode == "P" and "transparency" in source.info
            ):
                rgba = source.convert("RGBA")
                background = Image.new("RGBA", rgba.size, "white")
                background.alpha_composite(rgba)
                normalized = background.convert("RGB")
            else:
                normalized = source.convert("RGB")
            output = io.BytesIO()
            normalized.save(
                output,
                format="JPEG",
                quality=SIGNATURE_JPEG_QUALITY,
                optimize=True,
            )
            return output.getvalue()
    except SignatureImageError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise SignatureImageError("signature_image_invalid") from exc
