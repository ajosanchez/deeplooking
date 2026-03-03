"""Application-wide constants for deeplooking."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Resolution:
    """Represents a display resolution."""

    name: str
    width: int
    height: int


# Predefined resolution options
RESOLUTION_1080P = Resolution(name="1080p (1920x1080)", width=1920, height=1080)
RESOLUTION_4K = Resolution(name="4K (3840x2160)", width=3840, height=2160)
PREDEFINED_RESOLUTIONS: list[Resolution] = [RESOLUTION_1080P, RESOLUTION_4K]

# UI constants
THUMBNAIL_SIZE: int = 200
MINI_THUMBNAIL_SIZE: int = 80
SLICE_RECT_COLOR: str = "#00FF00"
SLICE_RECT_WIDTH: int = 3

# Animation constants
ZOOM_ANIMATION_DURATION_MS: int = 2000
MAX_ANIMATION_TIME_FRACTION: float = 0.4

# Viewer constants
DEFAULT_SLICE_GRID_LANDSCAPE: tuple[int, int] = (4, 2)  # cols x rows
DEFAULT_SLICE_GRID_PORTRAIT: tuple[int, int] = (2, 4)  # cols x rows

# Supported image extensions
SUPPORTED_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"})

# Duration bounds (minutes)
DEFAULT_VIEWING_DURATION_MINUTES: int = 80
MIN_VIEWING_DURATION_MINUTES: int = 1
MAX_VIEWING_DURATION_MINUTES: int = 480
