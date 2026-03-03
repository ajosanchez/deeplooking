"""Tests for deeplooking data models."""

from pathlib import Path

from deeplooking.constants import RESOLUTION_1080P, RESOLUTION_4K
from deeplooking.models import PaintingConfig, SliceRegion, ViewingSession


class TestSliceRegion:
    def test_to_pixel_rect_full_image(self) -> None:
        region = SliceRegion(x=0.0, y=0.0, width=1.0, height=1.0)
        assert region.to_pixel_rect(1920, 1080) == (0, 0, 1920, 1080)

    def test_to_pixel_rect_top_left_quarter(self) -> None:
        region = SliceRegion(x=0.0, y=0.0, width=0.5, height=0.5)
        assert region.to_pixel_rect(1000, 800) == (0, 0, 500, 400)

    def test_to_pixel_rect_bottom_right_quarter(self) -> None:
        region = SliceRegion(x=0.5, y=0.5, width=0.5, height=0.5)
        assert region.to_pixel_rect(1000, 800) == (500, 400, 1000, 800)

    def test_to_pixel_rect_center_region(self) -> None:
        region = SliceRegion(x=0.25, y=0.25, width=0.5, height=0.5)
        assert region.to_pixel_rect(1000, 1000) == (250, 250, 750, 750)

    def test_to_pixel_rect_large_image(self) -> None:
        region = SliceRegion(x=0.0, y=0.0, width=0.25, height=0.5)
        assert region.to_pixel_rect(12406, 8224) == (0, 0, 3101, 4112)

    def test_frozen(self) -> None:
        region = SliceRegion(x=0.0, y=0.0, width=1.0, height=1.0)
        try:
            region.x = 0.5  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass


class TestPaintingConfig:
    def test_is_landscape_wide(self) -> None:
        config = PaintingConfig(image_path=Path("test.jpg"), image_width=1920, image_height=1080)
        assert config.is_landscape is True

    def test_is_landscape_square(self) -> None:
        config = PaintingConfig(image_path=Path("test.jpg"), image_width=1000, image_height=1000)
        assert config.is_landscape is True

    def test_is_portrait(self) -> None:
        config = PaintingConfig(image_path=Path("test.jpg"), image_width=1080, image_height=1920)
        assert config.is_landscape is False

    def test_total_views_no_slices(self) -> None:
        config = PaintingConfig(image_path=Path("test.jpg"), image_width=1920, image_height=1080)
        assert config.total_views == 1

    def test_total_views_with_slices(self) -> None:
        slices = [SliceRegion(x=0.0, y=0.0, width=0.25, height=0.5) for _ in range(8)]
        config = PaintingConfig(
            image_path=Path("test.jpg"),
            image_width=1920,
            image_height=1080,
            slices=slices,
        )
        assert config.total_views == 9  # 1 whole + 8 slices


class TestViewingSession:
    def test_total_views_single_painting(self) -> None:
        slices = [SliceRegion(x=0.0, y=0.0, width=0.25, height=0.5) for _ in range(8)]
        painting = PaintingConfig(
            image_path=Path("test.jpg"),
            image_width=1920,
            image_height=1080,
            slices=slices,
        )
        session = ViewingSession(paintings=[painting], duration_minutes=80, target_resolution=RESOLUTION_1080P)
        assert session.total_views == 9

    def test_total_views_two_paintings(self) -> None:
        slices = [SliceRegion(x=0.0, y=0.0, width=0.25, height=0.5) for _ in range(8)]
        paintings = [
            PaintingConfig(image_path=Path("a.jpg"), image_width=1920, image_height=1080, slices=slices),
            PaintingConfig(image_path=Path("b.jpg"), image_width=1920, image_height=1080, slices=list(slices)),
        ]
        session = ViewingSession(paintings=paintings, duration_minutes=80, target_resolution=RESOLUTION_1080P)
        assert session.total_views == 18  # 2 * (1 + 8)

    def test_time_per_view_seconds(self) -> None:
        slices = [SliceRegion(x=0.0, y=0.0, width=0.25, height=0.5) for _ in range(8)]
        paintings = [
            PaintingConfig(image_path=Path("a.jpg"), image_width=1920, image_height=1080, slices=slices),
            PaintingConfig(image_path=Path("b.jpg"), image_width=1920, image_height=1080, slices=list(slices)),
        ]
        session = ViewingSession(paintings=paintings, duration_minutes=80, target_resolution=RESOLUTION_4K)
        # 80 * 60 / 18 = 266.666...
        expected = (80 * 60) / 18
        assert abs(session.time_per_view_seconds - expected) < 0.001

    def test_time_per_view_zero_views(self) -> None:
        session = ViewingSession(paintings=[], duration_minutes=80, target_resolution=RESOLUTION_1080P)
        assert session.time_per_view_seconds == 0.0

    def test_time_per_view_no_slices(self) -> None:
        painting = PaintingConfig(image_path=Path("test.jpg"), image_width=1920, image_height=1080)
        session = ViewingSession(paintings=[painting], duration_minutes=10, target_resolution=RESOLUTION_1080P)
        # 1 view (whole image only), 10 * 60 / 1 = 600
        assert session.time_per_view_seconds == 600.0
