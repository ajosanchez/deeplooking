"""Shared test fixtures for deeplooking tests."""

import os
from pathlib import Path

import pytest
from PIL import Image

# Use offscreen Qt platform for headless testing
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from deeplooking.constants import RESOLUTION_1080P
from deeplooking.models import PaintingConfig, SliceRegion, ViewingSession


@pytest.fixture
def tmp_image_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with test images."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    return img_dir


@pytest.fixture
def landscape_image_path(tmp_image_dir: Path) -> Path:
    """Create a small landscape test image (400x200)."""
    path = tmp_image_dir / "landscape.png"
    img = Image.new("RGB", (400, 200), color=(100, 150, 200))
    img.save(path)
    return path


@pytest.fixture
def portrait_image_path(tmp_image_dir: Path) -> Path:
    """Create a small portrait test image (200x400)."""
    path = tmp_image_dir / "portrait.png"
    img = Image.new("RGB", (200, 400), color=(200, 150, 100))
    img.save(path)
    return path


@pytest.fixture
def landscape_jpeg_path(tmp_image_dir: Path) -> Path:
    """Create a small landscape JPEG test image (800x400)."""
    path = tmp_image_dir / "landscape.jpg"
    img = Image.new("RGB", (800, 400), color=(50, 100, 150))
    img.save(path, format="JPEG")
    return path


@pytest.fixture
def sample_slices() -> list[SliceRegion]:
    """Eight default slices for a landscape image (4x2 grid)."""
    slices = []
    for row in range(2):
        for col in range(4):
            slices.append(SliceRegion(x=col * 0.25, y=row * 0.5, width=0.25, height=0.5))
    return slices


@pytest.fixture
def sample_painting(landscape_image_path: Path) -> PaintingConfig:
    """A PaintingConfig with 8 default slices."""
    slices = []
    for row in range(2):
        for col in range(4):
            slices.append(SliceRegion(x=col * 0.25, y=row * 0.5, width=0.25, height=0.5))
    return PaintingConfig(
        image_path=landscape_image_path,
        image_width=400,
        image_height=200,
        slices=slices,
    )


@pytest.fixture
def sample_session(sample_painting: PaintingConfig) -> ViewingSession:
    """A ViewingSession with one painting and 80 minutes."""
    return ViewingSession(
        paintings=[sample_painting],
        duration_minutes=80,
        target_resolution=RESOLUTION_1080P,
    )
