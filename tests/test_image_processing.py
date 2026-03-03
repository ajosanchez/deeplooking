"""Tests for deeplooking image processing utilities."""

from pathlib import Path

from PIL import Image

from deeplooking.image_processing import (
    compute_slice_rect_normalized,
    generate_default_slices,
    get_image_dimensions,
    load_thumbnail,
    pillow_to_qpixmap,
    scan_image_directory,
)


class TestLoadThumbnail:
    def test_landscape_thumbnail_respects_max_size(self, landscape_image_path: Path) -> None:
        thumb = load_thumbnail(landscape_image_path, max_size=100)
        assert thumb.width <= 100
        assert thumb.height <= 100

    def test_portrait_thumbnail_respects_max_size(self, portrait_image_path: Path) -> None:
        thumb = load_thumbnail(portrait_image_path, max_size=100)
        assert thumb.width <= 100
        assert thumb.height <= 100

    def test_jpeg_thumbnail(self, landscape_jpeg_path: Path) -> None:
        thumb = load_thumbnail(landscape_jpeg_path, max_size=100)
        assert thumb.width <= 100
        assert thumb.height <= 100

    def test_maintains_aspect_ratio(self, landscape_image_path: Path) -> None:
        thumb = load_thumbnail(landscape_image_path, max_size=100)
        # Original is 400x200 (2:1), thumbnail should be 100x50
        assert thumb.width == 100
        assert thumb.height == 50


class TestGetImageDimensions:
    def test_landscape_dimensions(self, landscape_image_path: Path) -> None:
        w, h = get_image_dimensions(landscape_image_path)
        assert w == 400
        assert h == 200

    def test_portrait_dimensions(self, portrait_image_path: Path) -> None:
        w, h = get_image_dimensions(portrait_image_path)
        assert w == 200
        assert h == 400


class TestPillowToQPixmap:
    def test_converts_rgb_image(self, qapp: object) -> None:
        img = Image.new("RGB", (50, 30), color=(255, 0, 0))
        pixmap = pillow_to_qpixmap(img)
        assert not pixmap.isNull()
        assert pixmap.width() == 50
        assert pixmap.height() == 30

    def test_converts_rgba_image(self, qapp: object) -> None:
        img = Image.new("RGBA", (50, 30), color=(255, 0, 0, 128))
        pixmap = pillow_to_qpixmap(img)
        assert not pixmap.isNull()
        assert pixmap.width() == 50
        assert pixmap.height() == 30


class TestGenerateDefaultSlices:
    def test_landscape_produces_8_slices(self) -> None:
        slices = generate_default_slices(1920, 1080)
        assert len(slices) == 8

    def test_portrait_produces_8_slices(self) -> None:
        slices = generate_default_slices(1080, 1920)
        assert len(slices) == 8

    def test_landscape_4x2_grid(self) -> None:
        slices = generate_default_slices(1920, 1080)
        # First row: 4 slices, each 0.25 wide, 0.5 tall
        assert slices[0].x == 0.0
        assert slices[0].y == 0.0
        assert slices[0].width == 0.25
        assert slices[0].height == 0.5
        # Last slice of first row
        assert slices[3].x == 0.75
        assert slices[3].y == 0.0
        # First slice of second row
        assert slices[4].x == 0.0
        assert slices[4].y == 0.5

    def test_portrait_2x4_grid(self) -> None:
        slices = generate_default_slices(1080, 1920)
        assert slices[0].width == 0.5
        assert slices[0].height == 0.25
        # Second column, first row
        assert slices[1].x == 0.5
        assert slices[1].y == 0.0

    def test_slices_cover_full_image(self) -> None:
        slices = generate_default_slices(1920, 1080)
        # All slices should tile the full image without gaps
        total_area = sum(s.width * s.height for s in slices)
        assert abs(total_area - 1.0) < 1e-10

    def test_scan_order(self) -> None:
        slices = generate_default_slices(1920, 1080)
        # Should go left-to-right, top-to-bottom
        for i in range(len(slices) - 1):
            curr = slices[i]
            nxt = slices[i + 1]
            # Either same row and moving right, or next row
            if abs(curr.y - nxt.y) < 1e-10:
                assert nxt.x > curr.x
            else:
                assert nxt.y > curr.y


class TestScanImageDirectory:
    def test_finds_images(self, tmp_image_dir: Path, landscape_image_path: Path, portrait_image_path: Path) -> None:
        files = scan_image_directory(tmp_image_dir)
        assert len(files) == 2
        assert landscape_image_path in files
        assert portrait_image_path in files

    def test_ignores_non_image_files(self, tmp_image_dir: Path) -> None:
        (tmp_image_dir / "readme.txt").write_text("not an image")
        (tmp_image_dir / "data.csv").write_text("1,2,3")
        img = Image.new("RGB", (10, 10))
        img.save(tmp_image_dir / "test.png")
        files = scan_image_directory(tmp_image_dir)
        assert len(files) == 1

    def test_empty_directory(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        assert scan_image_directory(empty) == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        assert scan_image_directory(tmp_path / "nonexistent") == []

    def test_sorted_alphabetically(self, tmp_image_dir: Path) -> None:
        for name in ["c.png", "a.png", "b.png"]:
            img = Image.new("RGB", (10, 10))
            img.save(tmp_image_dir / name)
        files = scan_image_directory(tmp_image_dir)
        names = [f.name for f in files]
        assert names == sorted(names)


class TestComputeSliceRectNormalized:
    def test_small_resolution_large_image(self) -> None:
        # 1920x1080 viewport on a 12406x8224 image
        img_w, img_h = 12406, 8224
        w, h = compute_slice_rect_normalized(1920, 1080, img_w, img_h)
        assert w < 1.0
        assert h < 1.0
        # Pixel aspect ratio should match 1920/1080 = 16/9
        pixel_aspect = (w * img_w) / (h * img_h)
        assert abs(pixel_aspect - 1920 / 1080) < 0.01

    def test_resolution_equals_image(self) -> None:
        w, h = compute_slice_rect_normalized(1920, 1080, 1920, 1080)
        assert abs(w - 1.0) < 0.01
        assert abs(h - 1.0) < 0.01

    def test_4k_on_large_image(self) -> None:
        img_w, img_h = 12406, 8224
        w, h = compute_slice_rect_normalized(3840, 2160, img_w, img_h)
        assert w < 1.0
        assert h < 1.0
        pixel_aspect = (w * img_w) / (h * img_h)
        assert abs(pixel_aspect - 3840 / 2160) < 0.01

    def test_result_clamped_to_one(self) -> None:
        # Resolution larger than image in both dimensions
        w, h = compute_slice_rect_normalized(3840, 2160, 1000, 500)
        assert w <= 1.0
        assert h <= 1.0
