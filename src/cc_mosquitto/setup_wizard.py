"""First-run Setup Wizard for CC Mosquitto.

Guides non-technical users through broker configuration in four steps:

1. Welcome  — what CC Mosquitto is and why you need it
2. Network  — port and bind address with plain-language explanations
3. Security — username/password: why, and where to enter them later
4. Ready    — summary and next steps (start broker, configure sensors)

The wizard runs automatically on first launch and is also accessible
from the Help menu for reconfiguration.
"""

from __future__ import annotations

import socket

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .config import BrokerConfig


def _get_local_ips() -> list[str]:
    """Get this computer's primary IPv4 address.

    Uses a UDP socket connection to determine which interface routes
    to the internet — this reliably returns the LAN IP that other
    devices should use to reach this broker.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return [ip]
    except Exception:
        return ["(could not detect)"]


class SetupWizard(QDialog):
    """Step-by-step broker configuration wizard.

    Emits ``finished_config`` with a :class:`BrokerConfig` when the user
    clicks *Finish*.  The caller is responsible for saving and applying it.
    """

    finished_config = Signal(BrokerConfig)

    _NUM_STEPS = 4

    def __init__(self, config: BrokerConfig | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CC Mosquitto — Setup Wizard")
        self.setMinimumSize(560, 560)
        self.resize(580, 600)

        self._config = config or BrokerConfig()
        self._step = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Step indicator bar --------------------------------------------------
        self._step_bar = _StepBar(self._NUM_STEPS)
        root.addWidget(self._step_bar)

        # -- Pages (stacked) -----------------------------------------------------
        self._stack = QStackedWidget()
        self._stack.addWidget(self._page_welcome())
        self._stack.addWidget(self._page_network())
        self._stack.addWidget(self._page_security())
        self._stack.addWidget(self._page_ready())
        root.addWidget(self._stack, 1)

        # -- Navigation buttons --------------------------------------------------
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #444;")
        root.addWidget(sep)

        nav = QHBoxLayout()
        nav.setContentsMargins(16, 10, 16, 10)

        self._back_btn = QPushButton("Back")
        self._back_btn.setFixedWidth(90)
        self._back_btn.clicked.connect(self._go_back)
        nav.addWidget(self._back_btn)

        nav.addStretch()

        self._skip_btn = QPushButton("Skip Wizard")
        self._skip_btn.setFixedWidth(100)
        self._skip_btn.setStyleSheet("color: #888;")
        self._skip_btn.clicked.connect(self.reject)
        nav.addWidget(self._skip_btn)

        self._next_btn = QPushButton("Next")
        self._next_btn.setFixedWidth(90)
        self._next_btn.setDefault(True)
        self._next_btn.clicked.connect(self._go_next)
        nav.addWidget(self._next_btn)

        root.addLayout(nav)

        self._update_nav()

    # =====================================================================
    #  Page builders
    # =====================================================================

    def _page_welcome(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Welcome to CC Mosquitto")
        title.setFont(QFont("", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(8)

        intro = QLabel(
            "CC Mosquitto is a message broker for your IoT sensors and "
            "ChromaChecker Capture stations. It acts as a central hub — "
            "sensors send temperature, humidity, and other data here, and "
            "your Capture applications pick it up automatically.\n\n"
            "This wizard will help you configure the broker in a few "
            "simple steps. You can always change these settings later."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 13px; line-height: 1.5;")
        layout.addWidget(intro)

        layout.addSpacing(8)

        # Visual: how it works
        how_label = QLabel(
            '<div style="font-size: 13px; text-align: center;">'
            "<b>Sensors</b> (temperature, humidity) send data"
            "<br>&#x25BC;<br>"
            "<b>CC Mosquitto</b> (this app) receives and distributes"
            "<br>&#x25BC;<br>"
            "<b>ChromaChecker Capture</b> reads and reports to server"
            "</div>"
        )
        how_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        how_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(how_label)

        layout.addStretch()

        hint = QLabel(
            '<span style="color: #888; font-size: 11px;">'
            "This wizard appears on first launch. You can run it again "
            "from Help → Setup Wizard."
            "</span>"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        return page

    def _page_network(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(10)

        title = QLabel("Step 2: Network Settings")
        title.setFont(QFont("", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        explain = QLabel(
            "These settings control how devices find and connect to "
            "your broker. In most cases the defaults work perfectly."
        )
        explain.setWordWrap(True)
        explain.setStyleSheet("color: #AAA; font-size: 12px;")
        layout.addWidget(explain)

        layout.addSpacing(8)

        # Port
        port_label = QLabel("<b>MQTT Port</b>")
        layout.addWidget(port_label)
        port_help = QLabel(
            '<span style="color: #888; font-size: 11px;">'
            "The standard MQTT port is 1883. Change it only if another "
            "service already uses this port. Every device (sensors, "
            "Capture stations) must use the same port number."
            "</span>"
        )
        port_help.setWordWrap(True)
        layout.addWidget(port_help)

        self._wiz_port = QSpinBox()
        self._wiz_port.setRange(1024, 65535)
        self._wiz_port.setValue(self._config.port)
        self._wiz_port.setFixedWidth(120)
        layout.addWidget(self._wiz_port)

        layout.addSpacing(12)

        # Bind address
        bind_label = QLabel("<b>Accept connections from</b>")
        layout.addWidget(bind_label)
        bind_help = QLabel(
            '<span style="color: #888; font-size: 11px;">'
            "Choose whether this broker accepts connections from other "
            "computers in your network, or only from this computer. "
            "For most setups you need \"All devices in my network\"."
            "</span>"
        )
        bind_help.setWordWrap(True)
        layout.addWidget(bind_help)

        self._bind_all = QCheckBox("All devices in my network (recommended)")
        self._bind_local = QCheckBox("This computer only (testing)")
        is_all = self._config.bind_address in ("0.0.0.0", "")
        self._bind_all.setChecked(is_all)
        self._bind_local.setChecked(not is_all)
        self._bind_all.toggled.connect(
            lambda c: self._bind_local.setChecked(not c) if c else None
        )
        self._bind_local.toggled.connect(
            lambda c: self._bind_all.setChecked(not c) if c else None
        )
        layout.addWidget(self._bind_all)
        layout.addWidget(self._bind_local)

        layout.addSpacing(12)

        # Detected network addresses — clearly labelled as live detection
        ips = _get_local_ips()
        if len(ips) == 1:
            ip_rows = f"<code style='font-size: 14px;'>{ips[0]}</code>"
        else:
            ip_rows = "<br>".join(
                f"<code style='font-size: 13px;'>{ip}</code>" for ip in ips
            )

        ip_label = QLabel(
            f'<div style="padding: 8px 0px; font-size: 12px;">'
            f'<span style="color: #888;">&#9432;</span> '
            f"<b>Detected network address{' (this computer)' if len(ips) == 1 else 'es (this computer)'}:</b>"
            f"<br><br>"
            f"{ip_rows}"
            f"<br><br>"
            f'<span style="color: #888;">If you have multiple addresses, '
            f"choose the one that is on the same network as your sensors "
            f"and Capture stations. You will need this address when "
            f"configuring other devices.</span>"
            f"</div>"
        )
        ip_label.setWordWrap(True)
        ip_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(ip_label)

        layout.addStretch()
        return page

    def _page_security(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(10)

        title = QLabel("Step 3: Security")
        title.setFont(QFont("", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        explain = QLabel(
            "A username and password prevent unauthorized devices from "
            "connecting to your broker. This is recommended — without it, "
            "anyone on your network can read your sensor data."
        )
        explain.setWordWrap(True)
        explain.setStyleSheet("color: #AAA; font-size: 12px;")
        layout.addWidget(explain)

        layout.addSpacing(8)

        self._wiz_auth = QCheckBox("Enable authentication (recommended)")
        self._wiz_auth.setChecked(self._config.require_auth)
        self._wiz_auth.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._wiz_auth)

        layout.addSpacing(4)

        # Credentials
        cred_frame = QFrame()
        cred_frame.setStyleSheet(
            "QFrame { padding: 4px; }"
        )
        cred_layout = QVBoxLayout(cred_frame)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Username:"))
        self._wiz_user = QLineEdit(self._config.username or "capture")
        row1.addWidget(self._wiz_user)
        cred_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Password:"))
        self._wiz_pass = QLineEdit(self._config.password)
        self._wiz_pass.setEchoMode(QLineEdit.EchoMode.Normal)
        self._wiz_pass.setPlaceholderText("Choose a password...")
        row2.addWidget(self._wiz_pass)
        cred_layout.addLayout(row2)

        layout.addWidget(cred_frame)

        self._wiz_auth.toggled.connect(cred_frame.setEnabled)
        cred_frame.setEnabled(self._config.require_auth)

        layout.addSpacing(8)

        # WHERE to enter these credentials — key explanation
        where_label = QLabel(
            '<div style="padding: 8px 0px; font-size: 12px;">'
            "<b>Where do I enter this password later?</b><br><br>"
            "You will need to enter the <u>same</u> username and password in "
            "three places:<br><br>"
            "<b>1.</b> <b>Here</b> — CC Mosquitto (you're doing this now) ✓<br><br>"
            "<b>2.</b> <b>ChromaChecker Capture</b> — on each computer running "
            "Capture, go to <i>Device → MQTT Broker → Setup</i> and enter "
            "the same credentials<br><br>"
            "<b>3.</b> <b>Each sensor</b> — in the sensor's web interface "
            "(Shelly: Settings → MQTT; Tasmota: Configuration → MQTT), "
            "enter the same credentials<br><br>"
            '<span style="color: #888;">All three must match. If any device '
            "has the wrong password, it won't be able to connect.</span>"
            "</div>"
        )
        where_label.setWordWrap(True)
        where_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(where_label)

        layout.addStretch()
        return page

    def _page_ready(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(10)

        title = QLabel("Ready to Start!")
        title.setFont(QFont("", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(8)

        # Summary will be populated dynamically in _update_summary
        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        self._summary_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._summary_label)

        layout.addSpacing(8)

        # Auto-start option
        self._wiz_autostart = QCheckBox(
            "Start broker automatically when I log in"
        )
        self._wiz_autostart.setChecked(self._config.autostart)
        layout.addWidget(self._wiz_autostart)

        # Start now option
        self._wiz_start_now = QCheckBox("Start the broker now")
        self._wiz_start_now.setChecked(True)
        self._wiz_start_now.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._wiz_start_now)

        layout.addSpacing(8)

        # Next steps
        next_label = QLabel(
            '<div style="padding: 8px 0px; font-size: 12px;">'
            "<b>What to do next:</b><br><br>"
            "<b>1.</b> Click <b>Finish</b> to save your settings and start "
            "the broker<br><br>"
            "<b>2.</b> On each ChromaChecker Capture computer, open "
            "<i>Device → MQTT Broker → Setup</i> and enter the broker "
            "address and credentials<br><br>"
            "<b>3.</b> Configure your sensors to connect to this broker "
            "(see the <b>Network Guide</b> tab for detailed instructions)<br><br>"
            "<b>4.</b> Watch the <b>Connection Log</b> tab — you should see "
            "devices connecting"
            "</div>"
        )
        next_label.setWordWrap(True)
        next_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(next_label)

        layout.addStretch()
        return page

    # =====================================================================
    #  Navigation
    # =====================================================================

    def _go_next(self) -> None:
        if self._step == self._NUM_STEPS - 1:
            self._finish()
            return
        self._step += 1
        if self._step == self._NUM_STEPS - 1:
            self._update_summary()
        self._stack.setCurrentIndex(self._step)
        self._step_bar.set_step(self._step)
        self._update_nav()

    def _go_back(self) -> None:
        if self._step == 0:
            return
        self._step -= 1
        self._stack.setCurrentIndex(self._step)
        self._step_bar.set_step(self._step)
        self._update_nav()

    def _update_nav(self) -> None:
        self._back_btn.setEnabled(self._step > 0)
        is_last = self._step == self._NUM_STEPS - 1
        self._next_btn.setText("Finish" if is_last else "Next")
        self._skip_btn.setVisible(self._step < self._NUM_STEPS - 1)

    def _update_summary(self) -> None:
        """Populate the summary label on the Ready page."""
        ips = _get_local_ips()
        port = self._wiz_port.value()
        auth = self._wiz_auth.isChecked()
        user = self._wiz_user.text().strip() or "capture"
        bind = "All devices" if self._bind_all.isChecked() else "This computer only"

        # Build address display: show all detected IPs
        if len(ips) > 1:
            addr_html = (
                f"<tr><td style='color:#888;'>Detected addresses:</td>"
                f"<td><b>{', '.join(ips)}</b></td></tr>"
            )
        else:
            addr_html = (
                f"<tr><td style='color:#888;'>This computer:</td>"
                f"<td><b>{ips[0] if ips else '?'}</b></td></tr>"
            )

        self._summary_label.setText(
            f'<div style="padding: 8px 0px; font-size: 12px;">'
            f"<b>Your configuration:</b><br><br>"
            f"<table cellpadding='4'>"
            f"{addr_html}"
            f"<tr><td style='color:#888;'>Port:</td>"
            f"<td><b>{port}</b></td></tr>"
            f"<tr><td style='color:#888;'>Accept connections:</td>"
            f"<td><b>{bind}</b></td></tr>"
            f"<tr><td style='color:#888;'>Authentication:</td>"
            f"<td><b>{'Enabled' if auth else 'Disabled'}</b></td></tr>"
            + (
                f"<tr><td style='color:#888;'>Username:</td>"
                f"<td><b>{user}</b></td></tr>"
                if auth
                else ""
            )
            + f"</table><br>"
            f'<span style="color: #888;">Other devices will connect to '
            f"this broker using one of the addresses above and port "
            f"<b>{port}</b>.</span>"
            f"</div>"
        )

    def _finish(self) -> None:
        """Apply wizard settings to config, emit signal, close."""
        self._config.port = self._wiz_port.value()
        self._config.bind_address = (
            "0.0.0.0" if self._bind_all.isChecked() else "127.0.0.1"
        )
        self._config.require_auth = self._wiz_auth.isChecked()
        self._config.username = self._wiz_user.text().strip() or "capture"
        self._config.password = self._wiz_pass.text()
        self._config.autostart = self._wiz_autostart.isChecked()
        self._config.persistence = True
        self._config.logging_enabled = True

        self._config.save()
        self.finished_config.emit(self._config)
        self.accept()

    @property
    def start_broker_now(self) -> bool:
        """Whether the user checked 'Start the broker now'."""
        return self._wiz_start_now.isChecked()


class _StepBar(QWidget):
    """Horizontal step indicator: ● — ● — ● — ● with labels."""

    _LABELS = ["Welcome", "Network", "Security", "Ready"]

    def __init__(self, num_steps: int, parent=None):
        super().__init__(parent)
        self._num = num_steps
        self._current = 0
        self.setFixedHeight(60)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(32, 12, 32, 8)

        self._dots: list[QLabel] = []
        self._titles: list[QLabel] = []

        for i in range(num_steps):
            col = QVBoxLayout()
            col.setAlignment(Qt.AlignmentFlag.AlignCenter)

            dot = QLabel("●")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet("font-size: 16px;")
            col.addWidget(dot)
            self._dots.append(dot)

            lbl = QLabel(self._LABELS[i] if i < len(self._LABELS) else f"Step {i+1}")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 10px;")
            col.addWidget(lbl)
            self._titles.append(lbl)

            if i < num_steps - 1:
                layout.addLayout(col)
                line = QLabel("—")
                line.setAlignment(Qt.AlignmentFlag.AlignCenter)
                line.setStyleSheet("color: #555; font-size: 14px;")
                layout.addWidget(line)
            else:
                layout.addLayout(col)

        self._refresh()

    def set_step(self, step: int) -> None:
        self._current = step
        self._refresh()

    def _refresh(self) -> None:
        for i, (dot, title) in enumerate(zip(self._dots, self._titles)):
            if i < self._current:
                # Completed
                dot.setStyleSheet("font-size: 16px; color: #27AE60;")
                dot.setText("✓")
                title.setStyleSheet("font-size: 10px; color: #27AE60;")
            elif i == self._current:
                # Current
                dot.setStyleSheet("font-size: 16px; color: #3498DB;")
                dot.setText("●")
                title.setStyleSheet(
                    "font-size: 10px; color: #3498DB; font-weight: bold;"
                )
            else:
                # Future
                dot.setStyleSheet("font-size: 16px; color: #555;")
                dot.setText("○")
                title.setStyleSheet("font-size: 10px; color: #555;")
