"""Main setup/configuration window for deeplooking."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from deeplooking.constants import (
    DEFAULT_VIEWING_DURATION_MINUTES,
    MAX_VIEWING_DURATION_MINUTES,
    MIN_VIEWING_DURATION_MINUTES,
    PREDEFINED_RESOLUTIONS,
    Resolution,
)
from deeplooking.image_processing import generate_default_slices
from deeplooking.models import PaintingConfig, ViewingSession
from deeplooking.widgets.image_selector import ImageSelectorWidget, ImageTile


class ResolutionComboBox(QWidget):
    """Dropdown for selecting target display resolution."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QComboBox

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Resolution:"))
        self._combo = QComboBox()
        self._resolutions: list[Resolution] = []

        # Add predefined resolutions
        for res in PREDEFINED_RESOLUTIONS:
            self._resolutions.append(res)
            self._combo.addItem(res.name)

        # Detect and add native resolution
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen is not None:
            size = screen.size()
            native = Resolution(
                name=f"Native ({size.width()}x{size.height()})",
                width=size.width(),
                height=size.height(),
            )
            # Only add if different from existing options
            existing = {(r.width, r.height) for r in self._resolutions}
            if (native.width, native.height) not in existing:
                self._resolutions.append(native)
                self._combo.addItem(native.name)

        layout.addWidget(self._combo)

    @property
    def selected_resolution(self) -> Resolution:
        """Return the currently selected resolution."""
        return self._resolutions[self._combo.currentIndex()]


class SetupWindow(QMainWindow):
    """Main application window with setup controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("deeplooking")
        self.setMinimumSize(700, 600)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Title
        title = QLabel("DEEPLOOKING")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 10px;")
        main_layout.addWidget(title)

        subtitle = QLabel("Contemplative Art Viewer")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; color: #888; padding-bottom: 10px;")
        main_layout.addWidget(subtitle)

        # Duration
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Duration:"))
        self._duration_spin = QSpinBox()
        self._duration_spin.setRange(MIN_VIEWING_DURATION_MINUTES, MAX_VIEWING_DURATION_MINUTES)
        self._duration_spin.setValue(DEFAULT_VIEWING_DURATION_MINUTES)
        self._duration_spin.setSuffix(" minutes")
        duration_layout.addWidget(self._duration_spin)
        duration_layout.addStretch()
        main_layout.addLayout(duration_layout)

        # Resolution
        self._resolution_combo = ResolutionComboBox()
        main_layout.addWidget(self._resolution_combo)

        # Folder browser
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Image Folder:"))
        self._folder_input = QLineEdit()
        self._folder_input.setReadOnly(True)
        self._folder_input.setPlaceholderText("Select a folder...")
        folder_layout.addWidget(self._folder_input)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(browse_btn)
        main_layout.addLayout(folder_layout)

        # Image selector
        self._image_selector = ImageSelectorWidget()
        self._image_selector.selection_changed.connect(self._update_start_button)
        self._image_selector.set_custom_editor_callback(self._open_custom_slice_editor)
        main_layout.addWidget(self._image_selector)

        # Start button
        self._start_btn = QPushButton("Start Viewing")
        self._start_btn.setEnabled(False)
        self._start_btn.setMinimumHeight(40)
        self._start_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._start_btn.clicked.connect(self._start_viewing)
        main_layout.addWidget(self._start_btn)

    def _browse_folder(self) -> None:
        """Open a folder dialog and load images from the selected directory."""
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if folder:
            self._folder_input.setText(folder)
            self._image_selector.load_directory(Path(folder))
            self._update_start_button()

    def _update_start_button(self) -> None:
        """Enable/disable the start button based on selection state."""
        selected = self._image_selector.get_selected_tiles()
        self._start_btn.setEnabled(len(selected) > 0)

    def _open_custom_slice_editor(self, tile: ImageTile) -> None:
        """Open the SliceEditorDialog for the given tile using the current resolution."""
        from deeplooking.widgets.slice_editor import SliceEditorDialog

        if tile.image_width == 0 or tile.image_height == 0:
            QMessageBox.warning(
                self,
                "Image Not Loaded",
                f"Thumbnail for {tile.image_path.name} hasn't finished loading yet. "
                "Please wait a moment and try again.",
            )
            tile._slice_mode.setCurrentIndex(0)
            return

        resolution = self._resolution_combo.selected_resolution

        dialog = SliceEditorDialog(
            image_path=tile.image_path,
            image_width=tile.image_width,
            image_height=tile.image_height,
            target_resolution=resolution,
            parent=self,
        )
        if dialog.exec():
            slices = dialog.get_slices()
            if slices:
                tile.set_custom_slices(slices, resolution)
            else:
                QMessageBox.information(
                    self,
                    "No Slices Created",
                    "No custom slices were defined. Reverting to default slicing.",
                )
                tile._slice_mode.setCurrentIndex(0)
                tile.clear_custom_slices()
        else:
            tile._slice_mode.setCurrentIndex(0)
            tile.clear_custom_slices()

    def _build_session(self) -> ViewingSession | None:
        """Construct a ViewingSession from the current setup, or None if invalid."""
        selected_tiles = self._image_selector.get_selected_tiles()
        if not selected_tiles:
            return None

        resolution = self._resolution_combo.selected_resolution
        paintings: list[PaintingConfig] = []

        for tile in selected_tiles:
            config = PaintingConfig(
                image_path=tile.image_path,
                image_width=tile.image_width,
                image_height=tile.image_height,
                use_default_slicing=tile.use_default_slicing,
            )

            if tile.use_default_slicing:
                config.slices = generate_default_slices(config.image_width, config.image_height)
            else:
                # Custom slicing: use pre-stored slices if available and resolution matches
                if tile.custom_slices and tile.custom_slices_resolution == resolution:
                    config.slices = tile.custom_slices
                else:
                    # Slices not yet created or resolution changed; open editor as fallback
                    from deeplooking.widgets.slice_editor import SliceEditorDialog

                    dialog = SliceEditorDialog(
                        image_path=tile.image_path,
                        image_width=tile.image_width,
                        image_height=tile.image_height,
                        target_resolution=resolution,
                        parent=self,
                    )
                    if dialog.exec():
                        config.slices = dialog.get_slices()
                    else:
                        return None  # User cancelled

                if not config.slices:
                    QMessageBox.warning(
                        self,
                        "No Slices",
                        f"No custom slices were created for {tile.image_path.name}. "
                        "Please add at least one slice or use default slicing.",
                    )
                    return None

            paintings.append(config)

        return ViewingSession(
            paintings=paintings,
            duration_minutes=self._duration_spin.value(),
            target_resolution=resolution,
        )

    def _start_viewing(self) -> None:
        """Build the session and launch the viewer."""
        session = self._build_session()
        if session is None:
            return

        from deeplooking.widgets.viewer import ViewerWindow

        self._viewer = ViewerWindow(session, parent=None)
        self._viewer.viewing_finished.connect(self._on_viewing_finished)
        self._viewer.showFullScreen()
        self.hide()

    def _on_viewing_finished(self) -> None:
        """Handle viewer closing — return to setup screen."""
        self._viewer.close()
        self._viewer.deleteLater()
        self.show()
