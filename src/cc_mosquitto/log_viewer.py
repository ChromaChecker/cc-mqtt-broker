"""Live log viewer widget for Mosquitto broker output.

Provides two views:
1. Activity log — user-friendly event display (connections, errors)
2. Raw log — full Mosquitto output for troubleshooting

The activity log filters out noisy startup messages and shows only
events that matter to the end user: who connected, who disconnected,
errors, and message flow summary.
"""

from __future__ import annotations

import re
from datetime import datetime

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QTextCharFormat
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# Maximum lines kept in each log viewer.
_MAX_LINES = 3000

# Mosquitto log lines we skip in user-friendly view (startup noise).
_SKIP_PATTERNS = [
    "mosquitto version",
    "config loaded",
    "bridge support",
    "persistence support",
    "tls support",
    "tls-psk support",
    "websockets support",
    "plugin builtin",
    "opening ipv",
    "starting in local",
    "create a configuration",
    "for more details",
    "using default config",
    "saving in-memory",
    "info: running mosquitto",
]


def _timestamp() -> str:
    """Return a short HH:MM:SS timestamp."""
    return datetime.now().strftime("%H:%M:%S")


def _extract_client_id(line: str) -> str:
    """Try to extract a client identifier from a Mosquitto log line."""
    # Patterns: "New client connected from 192.168.1.5:54321 as capture_rht"
    #           "Client capture_rht disconnected"
    m = re.search(r"as\s+(\S+)", line)
    if m:
        return m.group(1)
    m = re.search(r"Client\s+(\S+)", line)
    if m:
        return m.group(1)
    return ""


def _extract_ip(line: str) -> str:
    """Extract IP address from a log line."""
    m = re.search(r"from\s+([\d.]+)", line)
    return m.group(1) if m else ""


class LogViewer(QWidget):
    """Dual-mode log viewer: Activity (user-friendly) and Raw (debug).

    Signals:
        client_count_changed(int): Emitted when connected client count changes.
    """

    client_count_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client_count = 0
        self._known_clients: dict[str, str] = {}  # client_id → ip

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # -- Toolbar ----------------------------------------------------------
        toolbar = QHBoxLayout()

        self._view_combo = QComboBox()
        self._view_combo.addItems(["Activity", "Raw Log"])
        self._view_combo.currentIndexChanged.connect(self._on_view_changed)
        toolbar.addWidget(QLabel("View:"))
        toolbar.addWidget(self._view_combo)

        toolbar.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        # -- Stacked views ----------------------------------------------------
        self._stack = QStackedWidget()

        # Activity view (user-friendly)
        self._activity = QPlainTextEdit()
        self._activity.setReadOnly(True)
        self._activity.setMaximumBlockCount(_MAX_LINES)
        self._activity.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Menlo", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._activity.setFont(font)
        self._stack.addWidget(self._activity)

        # Raw log view
        self._raw = QPlainTextEdit()
        self._raw.setReadOnly(True)
        self._raw.setMaximumBlockCount(_MAX_LINES)
        self._raw.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._raw.setFont(font)
        self._stack.addWidget(self._raw)

        layout.addWidget(self._stack)

        # Pre-build text formats
        self._fmt_info = QTextCharFormat()
        self._fmt_info.setForeground(QColor("#AAAAAA"))

        self._fmt_connect = QTextCharFormat()
        self._fmt_connect.setForeground(QColor("#27AE60"))

        self._fmt_disconnect = QTextCharFormat()
        self._fmt_disconnect.setForeground(QColor("#E67E22"))

        self._fmt_error = QTextCharFormat()
        self._fmt_error.setForeground(QColor("#E74C3C"))

        self._fmt_subscribe = QTextCharFormat()
        self._fmt_subscribe.setForeground(QColor("#3498DB"))

        self._fmt_raw = QTextCharFormat()
        self._fmt_raw.setForeground(QColor("#888888"))

    @Slot(str)
    def append_line(self, line: str) -> None:
        """Process a Mosquitto log line: add to raw view, parse for activity."""
        # Always add to raw log
        self._append_raw(line)

        # Parse for activity view
        self._parse_for_activity(line)

    def _append_raw(self, line: str) -> None:
        """Append a line to the raw log view."""
        fmt = self._classify_raw(line)
        cursor = self._raw.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(line + "\n", fmt)
        sb = self._raw.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _append_activity(self, text: str, fmt: QTextCharFormat) -> None:
        """Append a user-friendly event to the activity view."""
        cursor = self._activity.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text + "\n", fmt)
        sb = self._activity.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _parse_for_activity(self, line: str) -> None:
        """Extract user-meaningful events from a Mosquitto log line."""
        low = line.lower()

        # Skip startup noise
        for pattern in _SKIP_PATTERNS:
            if pattern in low:
                return

        ts = _timestamp()

        # -- Client connected -------------------------------------------------
        if "new connection" in low or "new client" in low:
            client_id = _extract_client_id(line)
            ip = _extract_ip(line)
            if client_id:
                self._known_clients[client_id] = ip
                self._client_count += 1
                self.client_count_changed.emit(self._client_count)
                display = f"{client_id} ({ip})" if ip else client_id
                self._append_activity(
                    f"  {ts}  \u2713  Connected: {display}",
                    self._fmt_connect,
                )
            return

        # -- Client disconnected ----------------------------------------------
        if "disconnected" in low:
            client_id = _extract_client_id(line)
            if client_id:
                self._known_clients.pop(client_id, None)
                self._client_count = max(0, self._client_count - 1)
                self.client_count_changed.emit(self._client_count)
                self._append_activity(
                    f"  {ts}  \u2717  Disconnected: {client_id}",
                    self._fmt_disconnect,
                )
            return

        # -- Subscription -----------------------------------------------------
        if "subscri" in low:
            client_id = _extract_client_id(line)
            # Extract topic from "... on topic zigbee2mqtt/#"
            m = re.search(r"topic\s+(\S+)", line, re.IGNORECASE)
            topic = m.group(1) if m else "?"
            if client_id:
                self._append_activity(
                    f"  {ts}  \u266B  {client_id} subscribed to: {topic}",
                    self._fmt_subscribe,
                )
            return

        # -- Errors / warnings ------------------------------------------------
        if "error" in low or "warning" in low:
            # Strip the timestamp prefix from Mosquitto
            clean = re.sub(r"^\d+:\s*", "", line).strip()
            self._append_activity(
                f"  {ts}  \u26A0  {clean}",
                self._fmt_error,
            )
            return

        # -- Broker running/stopped -------------------------------------------
        if "running" in low and "mosquitto" in low:
            self._append_activity(
                f"  {ts}  \u25B6  Broker started",
                self._fmt_connect,
            )
            return

        if "terminating" in low:
            self._client_count = 0
            self.client_count_changed.emit(0)
            self._append_activity(
                f"  {ts}  \u25A0  Broker stopped",
                self._fmt_disconnect,
            )
            return

    def _classify_raw(self, line: str) -> QTextCharFormat:
        """Colour-code a raw log line."""
        low = line.lower()
        if "error" in low or "warning" in low:
            return self._fmt_error
        if "new connection" in low or "new client" in low:
            return self._fmt_connect
        if "disconnected" in low or "socket error" in low:
            return self._fmt_disconnect
        if "subscri" in low:
            return self._fmt_subscribe
        return self._fmt_raw

    @Slot(int)
    def _on_view_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    @Slot()
    def _on_clear(self) -> None:
        self._activity.clear()
        self._raw.clear()
