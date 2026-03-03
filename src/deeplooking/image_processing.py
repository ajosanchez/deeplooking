"""Image processing utilities for deeplooking."""

from pathlib import Path

from PIL import Image
from PySide6.QtGui import QImage, QPixmap

from deeplooking.constants import (
    DEFAULT_SLICE_GRID_LANDSCAPE,
    DEFAULT_SLICE_GRID_PORTRAIT,
    SUPPORTED_IMAGE_EXTENSIONS,
    THUMBNAIL_SIZE,
)
from deeplooking.models import SliceRegion


def load_thumbnail(image_path: Path, max_size: int = THUMBNAIL_SIZE) -> Image.Image:
    """Load a thumbnail using Pillow's draft() for fast JPEG decoding.

    For large JPEGs, draft() decodes at a reduced resolution before resizing,
    dramatically reducing memory usage and load time.
    """
    img = Image.open(image_path)
    if image_path.suffix.lower() in {".jpg", ".jpeg"}:
        scale = max(img.width, img.height) / max_size
        if scale > 8:
            img.draft("RGB", (img.width // 8, img.height // 8))
        elif scale > 4:
            img.draft("RGB", (img.width // 4, img.height // 4))
        elif scale > 2:
            img.draft("RGB", (img.width // 2, img.height // 2))
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return img


def get_image_dimensions(image_path: Path) -> tuple[int, int]:
    """Read image dimensions without loading full pixel data."""
    with Image.open(image_path) as img:
        return img.size


def pillow_to_qpixmap(pil_image: Image.Image) -> QPixmap:
    """Convert a Pillow Image to a Qt QPixmap."""
    if pil_image.mode != "RGBA":
        pil_image = pil_image.convert("RGBA")
    data = pil_image.tobytes("raw", "RGBA")
    qimage = QImage(data, pil_image.width, pil_image.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


def generate_default_slices(image_width: int, image_height: int) -> list[SliceRegion]:
    """Generate 8 equal slices in scan order (left-to-right, top-to-bottom).

    Landscape images use a 4x2 grid (4 columns, 2 rows).
    Portrait images use a 2x4 grid (2 columns, 4 rows).
    """
    is_landscape = image_width >= image_height
    cols, rows = DEFAULT_SLICE_GRID_LANDSCAPE if is_landscape else DEFAULT_SLICE_GRID_PORTRAIT
    slices: list[SliceRegion] = []
    slice_w = 1.0 / cols
    slice_h = 1.0 / rows
    for row in range(rows):
        for col in range(cols):
            slices.append(
                SliceRegion(
                    x=col * slice_w,
                    y=row * slice_h,
                    width=slice_w,
                    height=slice_h,
                )
            )
    return slices


def scan_image_directory(directory: Path) -> list[Path]:
    """Scan a directory for supported image files, sorted alphabetically."""
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS)


def compute_slice_rect_normalized(
    target_resolution_width: int,
    target_resolution_height: int,
    image_width: int,
    image_height: int,
) -> tuple[float, float]:
    """Compute the normalized width and height of the slice rectangle.

    The rectangle represents a viewport-sized window into the image,
    with aspect ratio matching the target resolution and size proportional
    to target_resolution / image_dimensions.

    Returns (normalized_width, normalized_height) clamped to [0, 1].
    """
    target_aspect = target_resolution_width / target_resolution_height

    norm_w = min(1.0, target_resolution_width / image_width)
    norm_h = min(1.0, target_resolution_height / image_height)

    # Check pixel aspect ratio of the rect: (norm_w * image_width) / (norm_h * image_height)
    # Adjust to match target aspect ratio
    pixel_aspect = (norm_w * image_width) / (norm_h * image_height)

    if pixel_aspect > target_aspect:
        # Width too large; reduce to match target aspect
        norm_w = target_aspect * norm_h * image_height / image_width
    elif pixel_aspect < target_aspect:
        # Height too large; reduce to match target aspect
        norm_h = norm_w * image_width / (target_aspect * image_height)

    return (min(1.0, norm_w), min(1.0, norm_h))
