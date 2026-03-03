"""Custom slicing dialog with interactive green rectangle overlay."""

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from deeplooking.constants import MINI_THUMBNAIL_SIZE, Resolution, SLICE_RECT_COLOR, SLICE_RECT_WIDTH
from deeplooking.image_processing import compute_slice_rect_normalized, load_thumbnail, pillow_to_qpixmap
from deeplooking.models import SliceRegion

EDITOR_THUMBNAIL_MAX = 800


class SliceMiniThumbnail(QWidget):
    """Mini thumbnail preview of a stamped slice with a remove button."""

    remove_clicked = Signal(int)

    def __init__(self, index: int, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        label = QLabel()
        scaled = pixmap.scaled(
            MINI_THUMBNAIL_SIZE,
            MINI_THUMBNAIL_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        label.setPixmap(scaled)
        layout.addWidget(label)

        num_label = QLabel(f"#{index + 1}")
        layout.addWidget(num_label)

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(24, 24)
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self._index))
        layout.addWidget(remove_btn)


class SliceScene(QGraphicsScene):
    """Graphics scene that handles click-to-stamp interaction."""

    slice_stamped = Signal(float, float)  # normalized x, y of the stamp

    def __init__(
        self,
        pixmap_item: QGraphicsPixmapItem,
        rect_width_norm: float,
        rect_height_norm: float,
        parent: object = None,
    ) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._pixmap_item = pixmap_item
        self._rect_width_norm = rect_width_norm
        self._rect_height_norm = rect_height_norm
        self._img_w = float(pixmap_item.pixmap().width())
        self._img_h = float(pixmap_item.pixmap().height())

        # Green selection rectangle
        rect_w = self._rect_width_norm * self._img_w
        rect_h = self._rect_height_norm * self._img_h
        pen = QPen(QColor(SLICE_RECT_COLOR), SLICE_RECT_WIDTH)
        brush = QBrush(QColor(0, 255, 0, 40))
        self._selector_rect = self.addRect(QRectF(0, 0, rect_w, rect_h), pen, brush)
        self._selector_rect.setZValue(10)

        self._dragging = False
        self._drag_offset_x = 0.0
        self._drag_offset_y = 0.0

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Start dragging if click is on the selector rect, otherwise stamp."""
        pos = event.scenePos()
        rect = self._selector_rect.rect()
        rect_scene = self._selector_rect.mapToScene(rect).boundingRect()

        if rect_scene.contains(pos):
            self._dragging = True
            self._drag_offset_x = pos.x() - rect_scene.x()
            self._drag_offset_y = pos.y() - rect_scene.y()
        else:
            # Move rect to click position (centered), then stamp
            self._move_rect_centered(pos.x(), pos.y())
            self._stamp()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Drag the selector rectangle."""
        if self._dragging:
            pos = event.scenePos()
            new_x = pos.x() - self._drag_offset_x
            new_y = pos.y() - self._drag_offset_y
            self._move_rect_to(new_x, new_y)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """End dragging."""
        self._dragging = False

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Double-click to stamp at current position."""
        self._stamp()

    def _move_rect_centered(self, cx: float, cy: float) -> None:
        """Move the selector rect so it's centered at (cx, cy), clamped to bounds."""
        rect = self._selector_rect.rect()
        new_x = cx - rect.width() / 2
        new_y = cy - rect.height() / 2
        self._move_rect_to(new_x, new_y)

    def _move_rect_to(self, x: float, y: float) -> None:
        """Move the selector rect to (x, y), clamped to image bounds."""
        rect = self._selector_rect.rect()
        max_x = self._img_w - rect.width()
        max_y = self._img_h - rect.height()
        clamped_x = max(0.0, min(x, max_x))
        clamped_y = max(0.0, min(y, max_y))
        self._selector_rect.setRect(QRectF(clamped_x, clamped_y, rect.width(), rect.height()))

    def _stamp(self) -> None:
        """Emit the current selector position as a normalized stamp."""
        rect = self._selector_rect.rect()
        norm_x = rect.x() / self._img_w
        norm_y = rect.y() / self._img_h
        self.slice_stamped.emit(norm_x, norm_y)

    def add_overlay(self, slice_region: SliceRegion) -> QGraphicsRectItem:
        """Add a semi-transparent overlay for a stamped slice."""
        x = slice_region.x * self._img_w
        y = slice_region.y * self._img_h
        w = slice_region.width * self._img_w
        h = slice_region.height * self._img_h
        pen = QPen(QColor(255, 200, 0), 2)
        brush = QBrush(QColor(255, 200, 0, 30))
        item = self.addRect(QRectF(x, y, w, h), pen, brush)
        item.setZValue(5)
        return item


class SliceEditorDialog(QDialog):
    """Dialog for interactively creating custom slice regions on a painting."""

    def __init__(
        self,
        image_path: Path,
        image_width: int,
        image_height: int,
        target_resolution: Resolution,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Custom Slicing - {image_path.name}")
        self.setMinimumSize(900, 600)

        self._image_path = image_path
        self._image_width = image_width
        self._image_height = image_height
        self._slices: list[SliceRegion] = []
        self._overlays: list[QGraphicsRectItem] = []

        # Compute normalized rect dimensions
        rect_w_norm, rect_h_norm = compute_slice_rect_normalized(
            target_resolution.width, target_resolution.height, image_width, image_height
        )
        self._rect_w_norm = rect_w_norm
        self._rect_h_norm = rect_h_norm

        # Load mid-resolution thumbnail for the editor
        pil_thumb = load_thumbnail(image_path, max_size=EDITOR_THUMBNAIL_MAX)
        self._thumb_pixmap = pillow_to_qpixmap(pil_thumb)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the dialog layout."""
        main_layout = QHBoxLayout(self)

        # Left: graphics view
        left_layout = QVBoxLayout()
        self._graphics_view = QGraphicsView()
        self._graphics_view.setRenderHint(self._graphics_view.renderHints())
        self._graphics_view.setDragMode(QGraphicsView.DragMode.NoDrag)

        pixmap_item = QGraphicsPixmapItem(self._thumb_pixmap)
        self._scene = SliceScene(pixmap_item, self._rect_w_norm, self._rect_h_norm)
        self._scene.addItem(pixmap_item)
        self._scene.setSceneRect(QRectF(0, 0, self._thumb_pixmap.width(), self._thumb_pixmap.height()))
        self._scene.slice_stamped.connect(self._on_stamp)

        self._graphics_view.setScene(self._scene)
        self._graphics_view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        left_layout.addWidget(self._graphics_view)

        hint_label = QLabel("Click to move & stamp | Double-click to stamp in place | Drag the green box to reposition")
        hint_label.setStyleSheet("color: #888; font-size: 11px;")
        left_layout.addWidget(hint_label)

        main_layout.addLayout(left_layout, stretch=3)

        # Right: slice list sidebar
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Slices:"))

        self._slice_scroll = QScrollArea()
        self._slice_scroll.setWidgetResizable(True)
        self._slice_scroll.setMinimumWidth(150)
        self._slice_list_widget = QWidget()
        self._slice_list_layout = QVBoxLayout(self._slice_list_widget)
        self._slice_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._slice_scroll.setWidget(self._slice_list_widget)
        right_layout.addWidget(self._slice_scroll)

        # Buttons
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        right_layout.addWidget(clear_btn)

        done_btn = QPushButton("Done")
        done_btn.setDefault(True)
        done_btn.clicked.connect(self.accept)
        right_layout.addWidget(done_btn)

        main_layout.addLayout(right_layout, stretch=1)

    def _on_stamp(self, norm_x: float, norm_y: float) -> None:
        """Handle a new slice stamp from the scene."""
        region = SliceRegion(x=norm_x, y=norm_y, width=self._rect_w_norm, height=self._rect_h_norm)
        self._slices.append(region)

        # Add overlay to scene
        overlay = self._scene.add_overlay(region)
        self._overlays.append(overlay)

        # Add mini thumbnail to sidebar
        self._add_slice_thumbnail(len(self._slices) - 1)

    def _add_slice_thumbnail(self, index: int) -> None:
        """Add a mini thumbnail widget for the slice at the given index."""
        region = self._slices[index]
        # Crop from the editor thumbnail
        thumb_w = self._thumb_pixmap.width()
        thumb_h = self._thumb_pixmap.height()
        crop_rect = QRectF(
            region.x * thumb_w,
            region.y * thumb_h,
            region.width * thumb_w,
            region.height * thumb_h,
        )
        cropped = self._thumb_pixmap.copy(crop_rect.toAlignedRect())

        mini = SliceMiniThumbnail(index, cropped, self._slice_list_widget)
        mini.remove_clicked.connect(self._remove_slice)
        self._slice_list_layout.addWidget(mini)

    def _remove_slice(self, index: int) -> None:
        """Remove a slice by index and rebuild the sidebar."""
        if 0 <= index < len(self._slices):
            self._slices.pop(index)
            # Remove overlay from scene
            overlay = self._overlays.pop(index)
            self._scene.removeItem(overlay)
            # Rebuild sidebar
            self._rebuild_sidebar()

    def _rebuild_sidebar(self) -> None:
        """Clear and rebuild all slice thumbnails in the sidebar."""
        # Remove all mini thumbnail widgets
        while self._slice_list_layout.count():
            item = self._slice_list_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        # Re-add all
        for i in range(len(self._slices)):
            self._add_slice_thumbnail(i)

    def _clear_all(self) -> None:
        """Remove all slices."""
        for overlay in self._overlays:
            self._scene.removeItem(overlay)
        self._overlays.clear()
        self._slices.clear()
        self._rebuild_sidebar()

    def get_slices(self) -> list[SliceRegion]:
        """Return the list of stamped slice regions."""
        return list(self._slices)

    def resizeEvent(self, event: object) -> None:
        """Refit the view when the dialog is resized."""
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._graphics_view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
