"""Tests for the SliceScene resize and interaction logic."""

from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor, QImage, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem

from deeplooking.constants import RESIZE_HANDLE_SIZE, SLICE_RECT_COLOR, SLICE_RECT_WIDTH
from deeplooking.widgets.slice_editor import SliceScene, _Corner, _InteractionMode, _SelectorRectItem


def _make_pixmap(width: int, height: int) -> QPixmap:
    """Create a solid-color QPixmap for testing."""
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(QColor(100, 100, 100))
    return QPixmap.fromImage(img)


def _make_scene(img_w: int = 800, img_h: int = 600, rect_w_norm: float = 0.25, rect_h_norm: float = 0.25) -> SliceScene:
    """Create a SliceScene with a test pixmap and given normalized rect dimensions."""
    pixmap = _make_pixmap(img_w, img_h)
    pixmap_item = QGraphicsPixmapItem(pixmap)
    return SliceScene(pixmap_item, rect_w_norm, rect_h_norm)


class TestCornerHitTest:
    """Tests for _hit_test_corner detection."""

    def test_hit_top_left_corner(self, qapp: QApplication) -> None:
        """Click at top-left corner of rect returns TOP_LEFT."""
        scene = _make_scene()
        rect = scene._selector_rect.rect()
        result = scene._hit_test_corner(rect.left(), rect.top())
        assert result == _Corner.TOP_LEFT

    def test_hit_top_right_corner(self, qapp: QApplication) -> None:
        """Click at top-right corner returns TOP_RIGHT."""
        scene = _make_scene()
        rect = scene._selector_rect.rect()
        result = scene._hit_test_corner(rect.right(), rect.top())
        assert result == _Corner.TOP_RIGHT

    def test_hit_bottom_left_corner(self, qapp: QApplication) -> None:
        """Click at bottom-left corner returns BOTTOM_LEFT."""
        scene = _make_scene()
        rect = scene._selector_rect.rect()
        result = scene._hit_test_corner(rect.left(), rect.bottom())
        assert result == _Corner.BOTTOM_LEFT

    def test_hit_bottom_right_corner(self, qapp: QApplication) -> None:
        """Click at bottom-right corner returns BOTTOM_RIGHT."""
        scene = _make_scene()
        rect = scene._selector_rect.rect()
        result = scene._hit_test_corner(rect.right(), rect.bottom())
        assert result == _Corner.BOTTOM_RIGHT

    def test_miss_center_of_rect(self, qapp: QApplication) -> None:
        """Click in center of rect misses all corners."""
        scene = _make_scene()
        rect = scene._selector_rect.rect()
        cx = rect.left() + rect.width() / 2
        cy = rect.top() + rect.height() / 2
        assert scene._hit_test_corner(cx, cy) is None

    def test_miss_outside_rect(self, qapp: QApplication) -> None:
        """Click far outside the rect misses all corners."""
        scene = _make_scene()
        assert scene._hit_test_corner(700.0, 500.0) is None

    def test_hit_within_threshold(self, qapp: QApplication) -> None:
        """Click within threshold pixels of a corner still registers."""
        scene = _make_scene()
        rect = scene._selector_rect.rect()
        # Offset by a few pixels from the corner
        offset = float(RESIZE_HANDLE_SIZE)
        result = scene._hit_test_corner(rect.left() + offset, rect.top() + offset)
        assert result == _Corner.TOP_LEFT


class TestResizeAlgorithm:
    """Tests for _resize_rect and aspect ratio enforcement."""

    def test_resize_maintains_aspect_ratio(self, qapp: QApplication) -> None:
        """After resize, rect pixel aspect matches the original target aspect."""
        scene = _make_scene(img_w=800, img_h=600, rect_w_norm=0.24, rect_h_norm=0.18)
        original_aspect = scene._aspect_ratio

        # Set up a resize from bottom-right corner
        scene._mode = _InteractionMode.RESIZING
        scene._resize_corner = _Corner.BOTTOM_RIGHT
        rect = scene._selector_rect.rect()
        scene._resize_anchor_x = rect.left()
        scene._resize_anchor_y = rect.top()

        # Resize to a larger size
        scene._resize_rect(rect.left() + 400.0, rect.top() + 300.0)

        new_rect = scene._selector_rect.rect()
        new_aspect = new_rect.width() / new_rect.height()
        assert abs(new_aspect - original_aspect) < 0.01

    def test_resize_does_not_go_below_minimum(self, qapp: QApplication) -> None:
        """Dragging corner inward respects minimum rect size."""
        scene = _make_scene(img_w=800, img_h=600, rect_w_norm=0.25, rect_h_norm=0.25)
        min_w = scene._min_width_norm * scene._img_w
        min_h = scene._min_height_norm * scene._img_h

        # Set up resize from bottom-right, try to make it tiny
        scene._mode = _InteractionMode.RESIZING
        scene._resize_corner = _Corner.BOTTOM_RIGHT
        rect = scene._selector_rect.rect()
        scene._resize_anchor_x = rect.left()
        scene._resize_anchor_y = rect.top()

        # Drag very close to anchor (try to make rect near-zero)
        scene._resize_rect(rect.left() + 5.0, rect.top() + 5.0)

        new_rect = scene._selector_rect.rect()
        assert new_rect.width() >= min_w - 0.01
        assert new_rect.height() >= min_h - 0.01

    def test_resize_clamps_to_image_bounds(self, qapp: QApplication) -> None:
        """Dragging corner beyond image edge keeps rect within bounds."""
        scene = _make_scene(img_w=800, img_h=600, rect_w_norm=0.25, rect_h_norm=0.25)

        # Set up resize from bottom-right
        scene._mode = _InteractionMode.RESIZING
        scene._resize_corner = _Corner.BOTTOM_RIGHT
        rect = scene._selector_rect.rect()
        scene._resize_anchor_x = rect.left()
        scene._resize_anchor_y = rect.top()

        # Drag way beyond image bounds
        scene._resize_rect(2000.0, 2000.0)

        new_rect = scene._selector_rect.rect()
        assert new_rect.right() <= 800.0 + 0.01
        assert new_rect.bottom() <= 600.0 + 0.01
        assert new_rect.left() >= -0.01
        assert new_rect.top() >= -0.01

    def test_resize_from_top_left_corner(self, qapp: QApplication) -> None:
        """Resizing from top-left keeps bottom-right as anchor."""
        scene = _make_scene(img_w=800, img_h=600, rect_w_norm=0.25, rect_h_norm=0.25)

        # Move rect to center first
        scene._move_rect_to(200.0, 150.0)
        rect = scene._selector_rect.rect()

        # Set up resize from top-left
        scene._mode = _InteractionMode.RESIZING
        scene._resize_corner = _Corner.TOP_LEFT
        scene._resize_anchor_x = rect.right()
        scene._resize_anchor_y = rect.bottom()

        anchor_right = rect.right()
        anchor_bottom = rect.bottom()

        # Drag top-left outward
        scene._resize_rect(50.0, 30.0)

        new_rect = scene._selector_rect.rect()
        # Anchor (bottom-right) should stay fixed
        assert abs(new_rect.right() - anchor_right) < 0.01
        assert abs(new_rect.bottom() - anchor_bottom) < 0.01
        # Rect should be larger
        assert new_rect.width() > rect.width()

    def test_resize_from_top_right_corner(self, qapp: QApplication) -> None:
        """Resizing from top-right keeps bottom-left as anchor."""
        scene = _make_scene(img_w=800, img_h=600, rect_w_norm=0.25, rect_h_norm=0.25)

        # Move rect to center
        scene._move_rect_to(200.0, 150.0)
        rect = scene._selector_rect.rect()

        scene._mode = _InteractionMode.RESIZING
        scene._resize_corner = _Corner.TOP_RIGHT
        scene._resize_anchor_x = rect.left()
        scene._resize_anchor_y = rect.bottom()

        anchor_left = rect.left()
        anchor_bottom = rect.bottom()

        # Drag outward to the right and up
        scene._resize_rect(600.0, 50.0)

        new_rect = scene._selector_rect.rect()
        assert abs(new_rect.left() - anchor_left) < 0.01
        assert abs(new_rect.bottom() - anchor_bottom) < 0.01

    def test_resize_from_bottom_left_corner(self, qapp: QApplication) -> None:
        """Resizing from bottom-left keeps top-right as anchor."""
        scene = _make_scene(img_w=800, img_h=600, rect_w_norm=0.25, rect_h_norm=0.25)

        # Move rect to center
        scene._move_rect_to(200.0, 150.0)
        rect = scene._selector_rect.rect()

        scene._mode = _InteractionMode.RESIZING
        scene._resize_corner = _Corner.BOTTOM_LEFT
        scene._resize_anchor_x = rect.right()
        scene._resize_anchor_y = rect.top()

        anchor_right = rect.right()
        anchor_top = rect.top()

        # Drag outward to the left and down
        scene._resize_rect(50.0, 500.0)

        new_rect = scene._selector_rect.rect()
        assert abs(new_rect.right() - anchor_right) < 0.01
        assert abs(new_rect.top() - anchor_top) < 0.01


class TestStampSignal:
    """Tests for the updated slice_stamped signal."""

    def test_stamp_emits_four_floats(self, qapp: QApplication) -> None:
        """slice_stamped signal carries (x, y, width, height)."""
        scene = _make_scene(img_w=800, img_h=600, rect_w_norm=0.25, rect_h_norm=0.25)

        received: list[tuple[float, float, float, float]] = []
        scene.slice_stamped.connect(lambda x, y, w, h: received.append((x, y, w, h)))

        scene._stamp()

        assert len(received) == 1
        x, y, w, h = received[0]
        assert isinstance(x, float)
        assert isinstance(y, float)
        assert isinstance(w, float)
        assert isinstance(h, float)

    def test_stamp_emits_correct_normalized_values(self, qapp: QApplication) -> None:
        """Stamp values match the current rect position and size."""
        scene = _make_scene(img_w=800, img_h=600, rect_w_norm=0.25, rect_h_norm=0.25)

        # Move rect to a known position
        scene._move_rect_to(100.0, 75.0)

        received: list[tuple[float, float, float, float]] = []
        scene.slice_stamped.connect(lambda x, y, w, h: received.append((x, y, w, h)))

        scene._stamp()

        x, y, w, h = received[0]
        assert abs(x - 100.0 / 800.0) < 0.001
        assert abs(y - 75.0 / 600.0) < 0.001
        assert abs(w - 0.25) < 0.001
        assert abs(h - 0.25) < 0.001

    def test_stamp_after_resize_uses_new_size(self, qapp: QApplication) -> None:
        """After resize, stamp emits the new width/height, not the original."""
        scene = _make_scene(img_w=800, img_h=600, rect_w_norm=0.25, rect_h_norm=0.25)

        # Resize the rect by directly calling _resize_rect
        scene._mode = _InteractionMode.RESIZING
        scene._resize_corner = _Corner.BOTTOM_RIGHT
        rect = scene._selector_rect.rect()
        scene._resize_anchor_x = rect.left()
        scene._resize_anchor_y = rect.top()
        scene._resize_rect(rect.left() + 400.0, rect.top() + 400.0)
        scene._mode = _InteractionMode.IDLE

        received: list[tuple[float, float, float, float]] = []
        scene.slice_stamped.connect(lambda x, y, w, h: received.append((x, y, w, h)))

        scene._stamp()

        _, _, w, h = received[0]
        # Width should be larger than original 0.25
        assert w > 0.25
        assert h > 0.25


class TestSelectorRectItem:
    """Tests for the _SelectorRectItem custom graphics item."""

    def test_creation(self, qapp: QApplication) -> None:
        """_SelectorRectItem can be created with handle size."""
        pen = QPen(QColor(SLICE_RECT_COLOR), SLICE_RECT_WIDTH)
        brush = QBrush(QColor(0, 255, 0, 40))
        item = _SelectorRectItem(QRectF(0, 0, 100, 80), pen, brush, RESIZE_HANDLE_SIZE)
        assert item.rect().width() == 100.0
        assert item.rect().height() == 80.0
        assert item._handle_size == RESIZE_HANDLE_SIZE


class TestInteractionModes:
    """Tests for the interaction mode state machine."""

    def test_initial_mode_is_idle(self, qapp: QApplication) -> None:
        """Scene starts in IDLE mode."""
        scene = _make_scene()
        assert scene._mode == _InteractionMode.IDLE

    def test_resize_corner_initially_none(self, qapp: QApplication) -> None:
        """No corner is selected initially."""
        scene = _make_scene()
        assert scene._resize_corner is None

    def test_move_after_resize_preserves_new_size(self, qapp: QApplication) -> None:
        """Moving the rect after resizing preserves the resized dimensions."""
        scene = _make_scene(img_w=800, img_h=600, rect_w_norm=0.25, rect_h_norm=0.25)

        # Resize the rect
        scene._mode = _InteractionMode.RESIZING
        scene._resize_corner = _Corner.BOTTOM_RIGHT
        rect = scene._selector_rect.rect()
        scene._resize_anchor_x = rect.left()
        scene._resize_anchor_y = rect.top()
        scene._resize_rect(rect.left() + 400.0, rect.top() + 400.0)

        resized_w = scene._selector_rect.rect().width()
        resized_h = scene._selector_rect.rect().height()

        # Simulate release (updates stored norms)
        scene._rect_width_norm = resized_w / scene._img_w
        scene._rect_height_norm = resized_h / scene._img_h
        scene._mode = _InteractionMode.IDLE

        # Now move the rect
        scene._move_rect_to(50.0, 50.0)

        moved_rect = scene._selector_rect.rect()
        assert abs(moved_rect.width() - resized_w) < 0.01
        assert abs(moved_rect.height() - resized_h) < 0.01
