"""About dialog for CC Mosquitto — version, credits, license information."""

from __future__ import annotations

import subprocess
import shutil

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import __version__


def _get_mosquitto_version() -> str:
    """Query the installed Mosquitto binary for its version string."""
    mosquitto = shutil.which("mosquitto")
    if not mosquitto:
        return "unknown"
    try:
        result = subprocess.run(
            [mosquitto, "--help"],
            capture_output=True, text=True, timeout=5,
        )
        # First line: "mosquitto version 2.1.2"
        for line in (result.stdout + result.stderr).splitlines():
            if "version" in line.lower():
                return line.strip()
        return "unknown"
    except Exception:
        return "unknown"


class AboutDialog(QDialog):
    """About CC Mosquitto — version info, credits, and license texts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About CC Mosquitto")
        self.setMinimumSize(520, 460)
        self.resize(540, 500)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # -- Header -----------------------------------------------------------
        header = QVBoxLayout()
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("CC Mosquitto")
        title.setFont(QFont("", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(title)

        subtitle = QLabel("MQTT Broker with Graphical Interface")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(subtitle)

        version_text = (
            f"Version {__version__}\n"
            f"{_get_mosquitto_version()}"
        )
        version_label = QLabel(version_text)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #888888;")
        header.addWidget(version_label)

        layout.addLayout(header)

        # -- Tabs: About / License / Third-Party ------------------------------
        tabs = QTabWidget()

        # Tab 1: About
        about_tab = QWidget()
        about_layout = QVBoxLayout(about_tab)
        about_browser = QTextBrowser()
        about_browser.setOpenExternalLinks(True)
        about_browser.setHtml(self._about_html())
        about_layout.addWidget(about_browser)
        tabs.addTab(about_tab, "About")

        # Tab 2: License (EPL-2.0)
        license_tab = QWidget()
        license_layout = QVBoxLayout(license_tab)
        license_browser = QTextBrowser()
        license_browser.setOpenExternalLinks(True)
        license_browser.setHtml(self._license_html())
        license_layout.addWidget(license_browser)
        tabs.addTab(license_tab, "License")

        # Tab 3: Third-Party Notices
        third_tab = QWidget()
        third_layout = QVBoxLayout(third_tab)
        third_browser = QTextBrowser()
        third_browser.setOpenExternalLinks(True)
        third_browser.setHtml(self._third_party_html())
        third_layout.addWidget(third_browser)
        tabs.addTab(third_tab, "Third-Party Notices")

        layout.addWidget(tabs)

        # -- Close button -----------------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    @staticmethod
    def _about_html() -> str:
        return """
        <h3>What is CC Mosquitto?</h3>
        <p>CC Mosquitto is a user-friendly MQTT broker application built on
        <a href="https://mosquitto.org/">Eclipse Mosquitto</a>. It provides
        a graphical interface for managing an MQTT message broker — no command
        line required.</p>

        <h3>What is it for?</h3>
        <p>CC Mosquitto acts as a central message hub for IoT devices in your
        local network. It is designed to work with
        <b>ChromaChecker Capture</b> for:</p>
        <ul>
            <li><b>RHT Sensors</b> — temperature and humidity monitoring
            (Shelly, Tasmota, Zigbee sensors)</li>
            <li><b>Signal Tower</b> — visual pass/fail indicators on the
            production floor</li>
            <li>Any other MQTT-compatible device</li>
        </ul>

        <h3>How does it work?</h3>
        <p>CC Mosquitto runs on one computer in your network. All other devices
        (sensors, ChromaChecker Capture stations) connect to it. Think of it as
        a "post office" for sensor messages — devices send data here, and
        applications pick it up.</p>

        <p style="color: #888;">
        &copy; 2026 ChromaChecker / Art-Fab Krzysztof Szafraniec<br>
        <a href="https://chromachecker.com">chromachecker.com</a>
        </p>
        """

    @staticmethod
    def _license_html() -> str:
        return """
        <h3>CC Mosquitto License</h3>

        <p>CC Mosquitto consists of two components with separate licenses:</p>

        <h4>1. Eclipse Mosquitto (MQTT Broker Engine)</h4>
        <p>Licensed under the <b>Eclipse Public License 2.0</b> (EPL-2.0).</p>
        <p>Source code is available at:<br>
        <a href="https://github.com/eclipse/mosquitto">
        https://github.com/eclipse/mosquitto</a></p>

        <p>The EPL-2.0 license permits use, modification, and redistribution.
        The source code for the Mosquitto component is made available as
        required by the license terms.</p>

        <p>Full license text:
        <a href="https://www.eclipse.org/legal/epl-2.0/">
        https://www.eclipse.org/legal/epl-2.0/</a></p>

        <h4>2. CC Mosquitto GUI</h4>
        <p>The graphical user interface is proprietary software.<br>
        &copy; 2026 ChromaChecker / Art-Fab Krzysztof Szafraniec.<br>
        All rights reserved.</p>
        """

    @staticmethod
    def _third_party_html() -> str:
        return """
        <h3>Third-Party Software</h3>
        <p>CC Mosquitto includes the following third-party components:</p>

        <table cellpadding="6" cellspacing="0" width="100%"
               style="border-collapse: collapse;">
        <tr style="background: #333;">
            <th align="left">Component</th>
            <th align="left">License</th>
            <th align="left">URL</th>
        </tr>
        <tr>
            <td><b>Eclipse Mosquitto</b></td>
            <td>EPL-2.0</td>
            <td><a href="https://mosquitto.org/">mosquitto.org</a></td>
        </tr>
        <tr style="background: #2a2a2a;">
            <td><b>PySide6 (Qt for Python)</b></td>
            <td>LGPL-3.0</td>
            <td><a href="https://www.qt.io/qt-for-python">qt.io</a></td>
        </tr>
        <tr>
            <td><b>Python</b></td>
            <td>PSF License</td>
            <td><a href="https://python.org">python.org</a></td>
        </tr>
        </table>

        <br>
        <p style="color: #888;">All trademarks are the property of their
        respective owners. Eclipse and Mosquitto are trademarks of the
        Eclipse Foundation.</p>
        """
