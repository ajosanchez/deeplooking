"""Data models for deeplooking viewing sessions."""

from dataclasses import dataclass, field
from pathlib import Path

from deeplooking.constants import Resolution


@dataclass(frozen=True)
class SliceRegion:
    """A rectangular region of an image defined in normalized coordinates (0.0-1.0).

    Using normalized coordinates decouples slice definitions from actual pixel
    dimensions, making them resolution-independent.
    """

    x: float
    y: float
    width: float
    height: float

    def to_pixel_rect(self, image_width: int, image_height: int) -> tuple[int, int, int, int]:
        """Convert to pixel coordinates (left, top, right, bottom) for Pillow cropping."""
        left = int(self.x * image_width)
        top = int(self.y * image_height)
        right = int((self.x + self.width) * image_width)
        bottom = int((self.y + self.height) * image_height)
        return (left, top, right, bottom)


@dataclass
class PaintingConfig:
    """Configuration for a single painting in the viewing session."""

    image_path: Path
    image_width: int
    image_height: int
    slices: list[SliceRegion] = field(default_factory=list)
    use_default_slicing: bool = True

    @property
    def is_landscape(self) -> bool:
        """Whether the image is landscape orientation."""
        return self.image_width >= self.image_height

    @property
    def total_views(self) -> int:
        """Total views: 1 whole image + N slices."""
        return 1 + len(self.slices)


@dataclass
class ViewingSession:
    """Complete session configuration passed from setup to viewer."""

    paintings: list[PaintingConfig]
    duration_minutes: int
    target_resolution: Resolution

    @property
    def total_views(self) -> int:
        """Sum of all views across all paintings."""
        return sum(p.total_views for p in self.paintings)

    @property
    def time_per_view_seconds(self) -> float:
        """Time allocated to each view (whole image or slice), including animation time."""
        total = self.total_views
        if total == 0:
            return 0.0
        return (self.duration_minutes * 60) / total
