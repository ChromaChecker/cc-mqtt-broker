"""System tray icon for CC Mosquitto.

Green icon = broker running, red = stopped.
Right-click menu: Start / Stop / Open Window / Quit.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def _make_circle_icon(color: str, size: int = 64) -> QIcon:
    """Create a simple filled-circle icon of the given colour."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(QColor(color).darker(120))
    margin = size // 8
    painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    """System tray icon with broker status indication.

    Signals:
        start_requested: User clicked Start from tray menu.
        stop_requested: User clicked Stop from tray menu.
        show_requested: User wants the main window visible.
        quit_requested: User chose Quit.
    """

    start_requested = Signal()
    stop_requested = Signal()
    show_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._icon_running = _make_circle_icon("#27AE60")  # green
        self._icon_stopped = _make_circle_icon("#E74C3C")  # red

        self.setIcon(self._icon_stopped)
        self.setToolTip("CC Mosquitto — Stopped")

        # Context menu
        menu = QMenu()

        self._start_action = QAction("Start", menu)
        self._start_action.triggered.connect(self.start_requested.emit)
        menu.addAction(self._start_action)

        self._stop_action = QAction("Stop", menu)
        self._stop_action.triggered.connect(self.stop_requested.emit)
        self._stop_action.setEnabled(False)
        menu.addAction(self._stop_action)

        menu.addSeparator()

        show_action = QAction("Open Window", menu)
        show_action.triggered.connect(self.show_requested.emit)
        menu.addAction(show_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

        # Left-click shows the main window
        self.activated.connect(self._on_activated)

    def set_running(self, running: bool) -> None:
        """Update icon and menu state to reflect broker status."""
        if running:
            self.setIcon(self._icon_running)
            self.setToolTip("CC Mosquitto — Running")
            self._start_action.setEnabled(False)
            self._stop_action.setEnabled(True)
        else:
            self.setIcon(self._icon_stopped)
            self.setToolTip("CC Mosquitto — Stopped")
            self._start_action.setEnabled(True)
            self._stop_action.setEnabled(False)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_requested.emit()
