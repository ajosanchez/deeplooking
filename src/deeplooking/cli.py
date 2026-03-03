"""Command-line entry point for deeplooking."""

import sys

from PySide6.QtWidgets import QApplication

from deeplooking.widgets.setup_screen import SetupWindow


def main() -> None:
    """Launch the deeplooking application."""
    app = QApplication(sys.argv)
    app.setApplicationName("deeplooking")
    window = SetupWindow()
    window.show()
    sys.exit(app.exec())
