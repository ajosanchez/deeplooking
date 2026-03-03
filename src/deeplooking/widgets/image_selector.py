"""Image browsing and selection widget with thumbnail grid."""

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from deeplooking.constants import THUMBNAIL_SIZE
from deeplooking.image_processing import get_image_dimensions, load_thumbnail, pillow_to_qpixmap


class ThumbnailLoader(QThread):
    """Background thread that loads image thumbnails one at a time."""

    thumbnail_ready = Signal(int, QPixmap, int, int)  # index, pixmap, width, height

    def __init__(self, image_paths: list[Path], max_size: int = THUMBNAIL_SIZE, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._image_paths = image_paths
        self._max_size = max_size

    def run(self) -> None:
        """Load thumbnails sequentially, emitting signals as each completes."""
        for i, path in enumerate(self._image_paths):
            try:
                width, height = get_image_dimensions(path)
                pil_thumb = load_thumbnail(path, self._max_size)
                pixmap = pillow_to_qpixmap(pil_thumb)
                self.thumbnail_ready.emit(i, pixmap, width, height)
            except Exception:
                pass  # Skip images that fail to load


class ImageTile(QWidget):
    """A single image tile with thumbnail, filename, checkbox, and slice mode selector."""

    selection_changed = Signal()

    def __init__(self, image_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.image_path = image_path
        self.image_width = 0
        self.image_height = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._thumbnail_label = QLabel()
        self._thumbnail_label.setFixedSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setStyleSheet("background-color: #2a2a2a; border: 1px solid #555;")
        layout.addWidget(self._thumbnail_label)

        name = image_path.stem
        if len(name) > 25:
            name = name[:22] + "..."
        self._name_label = QLabel(name)
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setToolTip(image_path.name)
        layout.addWidget(self._name_label)

        self._checkbox = QCheckBox("Select")
        self._checkbox.stateChanged.connect(lambda: self.selection_changed.emit())
        layout.addWidget(self._checkbox)

        self._slice_mode = QComboBox()
        self._slice_mode.addItems(["Default (8 slices)", "Custom"])
        self._slice_mode.setEnabled(False)
        self._checkbox.stateChanged.connect(lambda state: self._slice_mode.setEnabled(bool(state)))
        layout.addWidget(self._slice_mode)

    @property
    def is_selected(self) -> bool:
        """Whether the image is checked for viewing."""
        return self._checkbox.isChecked()

    @property
    def use_default_slicing(self) -> bool:
        """Whether default slicing mode is selected."""
        return self._slice_mode.currentIndex() == 0

    def set_thumbnail(self, pixmap: QPixmap, width: int, height: int) -> None:
        """Set the thumbnail image and store original dimensions."""
        self.image_width = width
        self.image_height = height
        scaled = pixmap.scaled(
            THUMBNAIL_SIZE,
            THUMBNAIL_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumbnail_label.setPixmap(scaled)


class ImageSelectorWidget(QWidget):
    """Scrollable grid of image thumbnails for selection."""

    selection_changed = Signal()

    COLUMNS = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tiles: list[ImageTile] = []
        self._loader: ThumbnailLoader | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setMinimumHeight(300)
        layout.addWidget(self._scroll)

        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._scroll.setWidget(self._grid_widget)

        self._placeholder = QLabel("Browse to a folder to see images")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid_layout.addWidget(self._placeholder, 0, 0, 1, self.COLUMNS)

    def load_directory(self, directory: Path) -> None:
        """Scan a directory and display image thumbnails."""
        from deeplooking.image_processing import scan_image_directory

        if self._loader is not None and self._loader.isRunning():
            self._loader.quit()
            self._loader.wait()

        # Clear existing tiles
        for tile in self._tiles:
            tile.setParent(None)
            tile.deleteLater()
        self._tiles.clear()

        if self._placeholder.parent() is not None:
            self._placeholder.setParent(None)

        image_paths = scan_image_directory(directory)

        if not image_paths:
            self._placeholder.setText("No images found in this folder")
            self._grid_layout.addWidget(self._placeholder, 0, 0, 1, self.COLUMNS)
            return

        for i, path in enumerate(image_paths):
            tile = ImageTile(path, self._grid_widget)
            tile.selection_changed.connect(self.selection_changed.emit)
            self._tiles.append(tile)
            row, col = divmod(i, self.COLUMNS)
            self._grid_layout.addWidget(tile, row, col)

        self._loader = ThumbnailLoader(image_paths, parent=self)
        self._loader.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._loader.start()

    def _on_thumbnail_ready(self, index: int, pixmap: QPixmap, width: int, height: int) -> None:
        """Update a tile with its loaded thumbnail."""
        if 0 <= index < len(self._tiles):
            self._tiles[index].set_thumbnail(pixmap, width, height)

    def get_selected_tiles(self) -> list[ImageTile]:
        """Return all tiles that are checked for viewing."""
        return [t for t in self._tiles if t.is_selected]
