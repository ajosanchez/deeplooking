"""Full-screen viewer with zoom animations for contemplative art viewing."""

from enum import Enum
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEasingCurve, QObject, QRectF, Qt, QTimeLine, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from deeplooking.constants import MAX_ANIMATION_TIME_FRACTION, ZOOM_ANIMATION_DURATION_MS
from deeplooking.models import PaintingConfig, SliceRegion, ViewingSession


class ViewerState(Enum):
    """State machine states for the viewer."""

    SHOWING_WHOLE = "showing_whole"
    ZOOMING_IN = "zooming_in"
    SHOWING_SLICE = "showing_slice"
    PANNING = "panning"
    LOADING = "loading"
    PAUSED = "paused"
    FINISHED = "finished"


class PausableTimer(QObject):
    """A timer that supports pause and resume by tracking remaining time."""

    timeout = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.timeout.emit)
        self._remaining_ms: int = 0
        self._elapsed_ms: int = 0
        self._running = False

    def start(self, duration_ms: int) -> None:
        """Start the timer for the given duration in milliseconds."""
        self._remaining_ms = duration_ms
        self._elapsed_ms = 0
        self._running = True
        self._timer.start(duration_ms)

    def pause(self) -> None:
        """Pause the timer, preserving remaining time."""
        if self._running:
            elapsed_since_start = self._timer.interval() - max(0, self._timer.remainingTime())
            self._elapsed_ms += elapsed_since_start
            self._remaining_ms = max(0, self._remaining_ms - elapsed_since_start)
            self._timer.stop()
            self._running = False

    def resume(self) -> None:
        """Resume the timer with the remaining time."""
        if not self._running and self._remaining_ms > 0:
            self._running = True
            self._timer.start(self._remaining_ms)

    def stop(self) -> None:
        """Stop the timer completely."""
        self._timer.stop()
        self._running = False
        self._remaining_ms = 0

    @property
    def is_running(self) -> bool:
        """Whether the timer is currently running (not paused)."""
        return self._running


class ImageLoader(QObject):
    """Loads a full-resolution image. Runs in the main thread but could be moved to QThread."""

    image_loaded = Signal(QPixmap)
    load_failed = Signal(str)

    def load(self, image_path: Path) -> None:
        """Load an image and emit the result."""
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self.load_failed.emit(f"Failed to load: {image_path}")
        else:
            self.image_loaded.emit(pixmap)


class ViewerWindow(QMainWindow):
    """Full-screen viewer that displays paintings with zoom animations."""

    viewing_finished = Signal()

    def __init__(self, session: ViewingSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._state = ViewerState.LOADING
        self._paused_state: ViewerState | None = None

        # Playback tracking
        self._painting_index = 0
        self._slice_index = 0
        self._time_per_view_ms = int(session.time_per_view_seconds * 1000)

        # Compute animation duration (capped so it doesn't dominate short view times)
        if self._time_per_view_ms > 0:
            max_anim = int(self._time_per_view_ms * MAX_ANIMATION_TIME_FRACTION)
            self._anim_duration_ms = min(ZOOM_ANIMATION_DURATION_MS, max_anim)
        else:
            self._anim_duration_ms = ZOOM_ANIMATION_DURATION_MS

        # UI setup
        self.setWindowTitle("deeplooking - Viewing")
        self.setStyleSheet("background-color: black;")
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self._view = QGraphicsView()
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setFrameShape(QGraphicsView.Shape.NoFrame)
        self._view.setStyleSheet("background-color: black;")
        self._view.setRenderHint(self._view.renderHints())
        layout.addWidget(self._view)

        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QColor(0, 0, 0))
        self._view.setScene(self._scene)

        self._pixmap_item: QGraphicsPixmapItem | None = None

        # Timer and animation
        self._view_timer = PausableTimer(self)
        self._view_timer.timeout.connect(self._on_view_timer_expired)
        self._zoom_timeline: QTimeLine | None = None
        self._zoom_from = QRectF()
        self._zoom_to = QRectF()
        self._zoom_callback: Callable[[], None] | None = None

        # Image loader
        self._loader = ImageLoader(self)
        self._loader.image_loaded.connect(self._on_image_loaded)
        self._loader.load_failed.connect(self._on_load_failed)

        # Start loading the first painting
        if self._session.paintings:
            self._load_current_painting()
        else:
            self._finish()

    def _load_current_painting(self) -> None:
        """Load the current painting's image."""
        self._state = ViewerState.LOADING
        painting = self._current_painting
        self._loader.load(painting.image_path)

    @property
    def _current_painting(self) -> PaintingConfig:
        """The painting currently being viewed."""
        return self._session.paintings[self._painting_index]

    def _on_image_loaded(self, pixmap: QPixmap) -> None:
        """Handle a successfully loaded image — start the viewing sequence."""
        self._scene.clear()
        self._pixmap_item = QGraphicsPixmapItem(pixmap)
        self._scene.addItem(self._pixmap_item)
        self._scene.setSceneRect(QRectF(0, 0, pixmap.width(), pixmap.height()))

        # Show the whole painting first
        self._slice_index = 0
        self._show_whole_image()

    def _on_load_failed(self, error: str) -> None:
        """Skip to the next painting if loading fails."""
        self._advance_to_next_painting()

    def _show_whole_image(self) -> None:
        """Display the full painting and start the view timer."""
        self._state = ViewerState.SHOWING_WHOLE
        self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._view_timer.start(self._time_per_view_ms)

    def _on_view_timer_expired(self) -> None:
        """Handle the view timer expiring — transition to the next state."""
        if self._state == ViewerState.SHOWING_WHOLE:
            # Time to zoom into the first slice
            if self._slice_index < len(self._current_painting.slices):
                self._start_zoom_in()
            else:
                self._advance_to_next_painting()

        elif self._state == ViewerState.SHOWING_SLICE:
            # Pan to the next slice or advance to the next painting
            self._slice_index += 1
            if self._slice_index < len(self._current_painting.slices):
                self._start_pan_to_next_slice()
            else:
                self._advance_to_next_painting()

    def _start_zoom_in(self) -> None:
        """Animate zooming in from the whole image to the current slice."""
        self._state = ViewerState.ZOOMING_IN
        slice_region = self._current_painting.slices[self._slice_index]
        from_rect = self._scene.sceneRect()
        to_rect = self._slice_to_scene_rect(slice_region)

        self._animate_zoom(from_rect, to_rect, self._on_zoom_in_complete)

    def _on_zoom_in_complete(self) -> None:
        """Zoom in finished — hold on the slice."""
        self._state = ViewerState.SHOWING_SLICE
        # Deduct animation time from the view time
        hold_time = max(100, self._time_per_view_ms - self._anim_duration_ms)
        self._view_timer.start(hold_time)

    def _start_pan_to_next_slice(self) -> None:
        """Animate panning from the previous slice to the current slice."""
        self._state = ViewerState.PANNING
        prev_region = self._current_painting.slices[self._slice_index - 1]
        curr_region = self._current_painting.slices[self._slice_index]
        from_rect = self._slice_to_scene_rect(prev_region)
        to_rect = self._slice_to_scene_rect(curr_region)
        self._animate_zoom(from_rect, to_rect, self._on_pan_complete)

    def _on_pan_complete(self) -> None:
        """Pan animation finished — hold on the new slice."""
        self._state = ViewerState.SHOWING_SLICE
        hold_time = max(100, self._time_per_view_ms - self._anim_duration_ms)
        self._view_timer.start(hold_time)

    def _advance_to_next_painting(self) -> None:
        """Move to the next painting or finish."""
        self._painting_index += 1
        if self._painting_index < len(self._session.paintings):
            self._load_current_painting()
        else:
            self._finish()

    def _finish(self) -> None:
        """Session complete."""
        self._state = ViewerState.FINISHED
        self._view_timer.stop()
        self.viewing_finished.emit()

    def _slice_to_scene_rect(self, region: SliceRegion) -> QRectF:
        """Convert a normalized SliceRegion to a QRectF in scene coordinates."""
        sr = self._scene.sceneRect()
        return QRectF(
            sr.x() + region.x * sr.width(),
            sr.y() + region.y * sr.height(),
            region.width * sr.width(),
            region.height * sr.height(),
        )

    def _animate_zoom(self, from_rect: QRectF, to_rect: QRectF, on_complete: Callable[[], None]) -> None:
        """Animate the view from one rectangle to another using QTimeLine."""
        self._zoom_from = from_rect
        self._zoom_to = to_rect
        self._zoom_callback = on_complete

        self._zoom_timeline = QTimeLine(self._anim_duration_ms, self)
        self._zoom_timeline.setFrameRange(0, 100)
        self._zoom_timeline.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._zoom_timeline.frameChanged.connect(self._on_zoom_frame)
        self._zoom_timeline.finished.connect(self._on_zoom_finished)
        self._zoom_timeline.start()

    def _on_zoom_frame(self, frame: int) -> None:
        """Interpolate between from_rect and to_rect at the given frame (0-100)."""
        t = frame / 100.0
        rect = QRectF(
            self._zoom_from.x() + t * (self._zoom_to.x() - self._zoom_from.x()),
            self._zoom_from.y() + t * (self._zoom_to.y() - self._zoom_from.y()),
            self._zoom_from.width() + t * (self._zoom_to.width() - self._zoom_from.width()),
            self._zoom_from.height() + t * (self._zoom_to.height() - self._zoom_from.height()),
        )
        self._view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def _on_zoom_finished(self) -> None:
        """Zoom animation complete — invoke the callback."""
        if self._zoom_timeline is not None:
            self._zoom_timeline.deleteLater()
            self._zoom_timeline = None
        if self._zoom_callback is not None:
            callback = self._zoom_callback
            self._zoom_callback = None
            callback()

    def _toggle_pause(self) -> None:
        """Pause or resume the viewing session."""
        if self._state == ViewerState.PAUSED:
            # Resume
            self._state = self._paused_state or ViewerState.SHOWING_WHOLE
            self._paused_state = None
            self._view_timer.resume()
            if self._zoom_timeline is not None:
                self._zoom_timeline.setPaused(False)
        elif self._state in (
            ViewerState.SHOWING_WHOLE,
            ViewerState.SHOWING_SLICE,
            ViewerState.ZOOMING_IN,
            ViewerState.PANNING,
        ):
            # Pause
            self._paused_state = self._state
            self._state = ViewerState.PAUSED
            self._view_timer.pause()
            if self._zoom_timeline is not None:
                self._zoom_timeline.setPaused(True)

    def _exit_to_setup(self) -> None:
        """Exit the viewer and return to the setup screen."""
        self._view_timer.stop()
        if self._zoom_timeline is not None:
            self._zoom_timeline.stop()
            self._zoom_timeline.deleteLater()
            self._zoom_timeline = None
        self.viewing_finished.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard controls during viewing."""
        if event.key() == Qt.Key.Key_Space:
            self._toggle_pause()
        elif event.key() == Qt.Key.Key_Escape:
            self._exit_to_setup()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event: object) -> None:
        """Refit the view on resize to maintain correct framing."""
        super().resizeEvent(event)  # type: ignore[arg-type]
        if self._state == ViewerState.SHOWING_WHOLE:
            self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        elif self._state == ViewerState.SHOWING_SLICE and self._slice_index < len(self._current_painting.slices):
            region = self._current_painting.slices[self._slice_index]
            self._view.fitInView(self._slice_to_scene_rect(region), Qt.AspectRatioMode.KeepAspectRatio)
