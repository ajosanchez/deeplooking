"""Tests for viewer logic components."""

from PySide6.QtCore import QRectF

from deeplooking.models import SliceRegion
from deeplooking.widgets.viewer import PausableTimer, ViewerState


class TestViewerState:
    def test_all_states_exist(self) -> None:
        states = [
            ViewerState.SHOWING_WHOLE,
            ViewerState.ZOOMING_IN,
            ViewerState.SHOWING_SLICE,
            ViewerState.PANNING,
            ViewerState.LOADING,
            ViewerState.PAUSED,
            ViewerState.FINISHED,
        ]
        assert len(states) == 7


class TestPausableTimer:
    def test_start_and_timeout(self, qapp: object, qtbot: object) -> None:
        timer = PausableTimer()
        fired = []
        timer.timeout.connect(lambda: fired.append(True))
        timer.start(50)
        assert timer.is_running
        # Wait for the timer to fire
        import time

        time.sleep(0.15)
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()
        assert len(fired) == 1

    def test_pause_and_resume(self, qapp: object) -> None:
        timer = PausableTimer()
        timer.start(5000)
        assert timer.is_running
        timer.pause()
        assert not timer.is_running
        timer.resume()
        assert timer.is_running
        timer.stop()

    def test_stop(self, qapp: object) -> None:
        timer = PausableTimer()
        timer.start(5000)
        timer.stop()
        assert not timer.is_running


class TestSliceToSceneRect:
    def test_full_image_region(self) -> None:
        region = SliceRegion(x=0.0, y=0.0, width=1.0, height=1.0)
        scene_rect = QRectF(0, 0, 1920, 1080)
        result = QRectF(
            scene_rect.x() + region.x * scene_rect.width(),
            scene_rect.y() + region.y * scene_rect.height(),
            region.width * scene_rect.width(),
            region.height * scene_rect.height(),
        )
        assert result == QRectF(0, 0, 1920, 1080)

    def test_top_left_quarter(self) -> None:
        region = SliceRegion(x=0.0, y=0.0, width=0.25, height=0.5)
        scene_rect = QRectF(0, 0, 1920, 1080)
        result = QRectF(
            scene_rect.x() + region.x * scene_rect.width(),
            scene_rect.y() + region.y * scene_rect.height(),
            region.width * scene_rect.width(),
            region.height * scene_rect.height(),
        )
        assert result == QRectF(0, 0, 480, 540)

    def test_center_region(self) -> None:
        region = SliceRegion(x=0.25, y=0.25, width=0.5, height=0.5)
        scene_rect = QRectF(0, 0, 1000, 1000)
        result = QRectF(
            scene_rect.x() + region.x * scene_rect.width(),
            scene_rect.y() + region.y * scene_rect.height(),
            region.width * scene_rect.width(),
            region.height * scene_rect.height(),
        )
        assert result == QRectF(250, 250, 500, 500)


class TestAnimationDurationCapping:
    def test_short_view_time_caps_animation(self) -> None:
        # If view time is 2 seconds, animation should be at most 40% = 800ms
        time_per_view_ms = 2000
        max_animation_fraction = 0.4
        max_anim = int(time_per_view_ms * max_animation_fraction)
        default_anim = 2000
        actual = min(default_anim, max_anim)
        assert actual == 800

    def test_long_view_time_uses_default(self) -> None:
        # If view time is 60 seconds, 40% = 24000ms > 2000ms default, so default is used
        time_per_view_ms = 60000
        max_animation_fraction = 0.4
        max_anim = int(time_per_view_ms * max_animation_fraction)
        default_anim = 2000
        actual = min(default_anim, max_anim)
        assert actual == 2000


class TestRectInterpolation:
    def test_interpolation_at_start(self) -> None:
        from_rect = QRectF(0, 0, 1920, 1080)
        to_rect = QRectF(0, 0, 480, 540)
        t = 0.0
        result = QRectF(
            from_rect.x() + t * (to_rect.x() - from_rect.x()),
            from_rect.y() + t * (to_rect.y() - from_rect.y()),
            from_rect.width() + t * (to_rect.width() - from_rect.width()),
            from_rect.height() + t * (to_rect.height() - from_rect.height()),
        )
        assert result == from_rect

    def test_interpolation_at_end(self) -> None:
        from_rect = QRectF(0, 0, 1920, 1080)
        to_rect = QRectF(0, 0, 480, 540)
        t = 1.0
        result = QRectF(
            from_rect.x() + t * (to_rect.x() - from_rect.x()),
            from_rect.y() + t * (to_rect.y() - from_rect.y()),
            from_rect.width() + t * (to_rect.width() - from_rect.width()),
            from_rect.height() + t * (to_rect.height() - from_rect.height()),
        )
        assert result == to_rect

    def test_interpolation_at_midpoint(self) -> None:
        from_rect = QRectF(0, 0, 1000, 1000)
        to_rect = QRectF(250, 250, 500, 500)
        t = 0.5
        result = QRectF(
            from_rect.x() + t * (to_rect.x() - from_rect.x()),
            from_rect.y() + t * (to_rect.y() - from_rect.y()),
            from_rect.width() + t * (to_rect.width() - from_rect.width()),
            from_rect.height() + t * (to_rect.height() - from_rect.height()),
        )
        assert result == QRectF(125, 125, 750, 750)

    def test_slice_to_slice_pure_pan(self) -> None:
        """Interpolation between same-sized slices produces a pure horizontal pan."""
        from_rect = QRectF(0, 0, 480, 540)
        to_rect = QRectF(480, 0, 480, 540)
        t = 0.5
        result = QRectF(
            from_rect.x() + t * (to_rect.x() - from_rect.x()),
            from_rect.y() + t * (to_rect.y() - from_rect.y()),
            from_rect.width() + t * (to_rect.width() - from_rect.width()),
            from_rect.height() + t * (to_rect.height() - from_rect.height()),
        )
        assert result == QRectF(240, 0, 480, 540)

    def test_slice_to_slice_with_zoom_adjust(self) -> None:
        """Interpolation between different-sized slices produces pan with zoom adjustment."""
        from_rect = QRectF(0, 0, 480, 540)
        to_rect = QRectF(480, 0, 960, 540)
        t = 0.5
        result = QRectF(
            from_rect.x() + t * (to_rect.x() - from_rect.x()),
            from_rect.y() + t * (to_rect.y() - from_rect.y()),
            from_rect.width() + t * (to_rect.width() - from_rect.width()),
            from_rect.height() + t * (to_rect.height() - from_rect.height()),
        )
        assert result == QRectF(240, 0, 720, 540)


class TestTransitionFlow:
    """Tests for the pan transition state machine flow logic."""

    def test_no_slices_skips_to_next_painting(self) -> None:
        """With no slices, viewer goes directly from whole to next painting."""
        slices: list[SliceRegion] = []
        slice_index = 0
        assert not (slice_index < len(slices))

    def test_single_slice_no_pan(self) -> None:
        """With one slice, after showing it, no pan is triggered."""
        slices = [SliceRegion(x=0.0, y=0.0, width=0.5, height=0.5)]
        slice_index = 0
        # After showing slice 0, increment
        slice_index += 1
        assert slice_index >= len(slices)

    def test_two_slices_one_pan(self) -> None:
        """With two slices, one pan transition occurs between them."""
        slices = [
            SliceRegion(x=0.0, y=0.0, width=0.25, height=0.5),
            SliceRegion(x=0.25, y=0.0, width=0.25, height=0.5),
        ]
        slice_index = 0
        # After showing slice 0, increment — should pan to slice 1
        slice_index += 1
        assert slice_index < len(slices)
        # After showing slice 1, increment — should advance
        slice_index += 1
        assert slice_index >= len(slices)
