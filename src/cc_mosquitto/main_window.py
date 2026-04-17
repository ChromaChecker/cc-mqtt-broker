"""Main window for CC Mosquitto — broker controls, log viewer, and help."""

from __future__ import annotations

import logging
import socket
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QCloseEvent, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .broker_manager import BrokerManager
from .config import BrokerConfig
from .log_viewer import LogViewer
from . import autostart as autostart_mod, __version__

logger = logging.getLogger(__name__)


def _get_local_ips() -> list[str]:
    """Get this computer's primary IPv4 address.

    Uses a UDP socket to determine which interface routes to the
    internet — reliably returns the LAN IP that other devices
    should connect to.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return [ip]
    except Exception:
        return ["(could not detect)"]


class MainWindow(QMainWindow):
    """Main window with three tabs: Broker, Network Guide, Connection Log."""

    def __init__(self, manager: BrokerManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._config = manager.config

        self.setWindowTitle("CC Mosquitto")
        self.setMinimumSize(540, 620)
        self.resize(560, 680)

        # -- Menu bar ---------------------------------------------------------
        self._setup_menu()

        # -- Central widget: tabs ---------------------------------------------
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 8, 12, 8)

        self._tabs = QTabWidget()
        main_layout.addWidget(self._tabs)

        # Tab 1: Broker
        self._tabs.addTab(self._create_broker_tab(), "Broker")

        # Tab 2: Network Guide
        self._tabs.addTab(self._create_network_guide_tab(), "Network Guide")

        # Tab 3: Connection Log
        self._log_viewer = LogViewer()
        self._log_viewer.client_count_changed.connect(self._on_client_count)
        self._tabs.addTab(self._log_viewer, "Connection Log")

        # -- Status bar -------------------------------------------------------
        self._clients_label = QLabel("Clients: 0")
        self.statusBar().addWidget(self._clients_label)
        self._status_bar_label = QLabel("")
        self.statusBar().addPermanentWidget(self._status_bar_label)

        # -- Connect signals --------------------------------------------------
        self._manager.started.connect(self._on_broker_started)
        self._manager.stopped.connect(self._on_broker_stopped)
        self._manager.error_occurred.connect(self._on_broker_error)
        self._manager.log_line_received.connect(self._log_viewer.append_line)

    # =====================================================================
    #  Menu bar
    # =====================================================================

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        # -- CC Mosquitto menu (macOS app menu) --------------------------------
        # On macOS, About and Preferences go in the app menu automatically
        # when we set the correct MenuRole.

        # About
        about_action = QAction("About CC Mosquitto...", self)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        about_action.triggered.connect(self._on_about)

        # Preferences (placeholder — opens Broker tab)
        prefs_action = QAction("Preferences...", self)
        prefs_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        prefs_action.triggered.connect(lambda: self._tabs.setCurrentIndex(0))

        # File menu (holds About and Prefs on non-macOS)
        file_menu = menubar.addMenu("File")
        file_menu.addAction(about_action)
        file_menu.addAction(prefs_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        network_guide_action = QAction("Network Setup Guide", self)
        network_guide_action.triggered.connect(lambda: self._tabs.setCurrentIndex(1))
        help_menu.addAction(network_guide_action)

        help_menu.addSeparator()

        # License Information submenu
        license_menu = help_menu.addMenu("License Information")

        epl_action = QAction("Eclipse Public License 2.0 (Mosquitto)...", self)
        epl_action.triggered.connect(self._on_show_epl)
        license_menu.addAction(epl_action)

        third_party_action = QAction("Third-Party Notices...", self)
        third_party_action.triggered.connect(self._on_show_third_party)
        license_menu.addAction(third_party_action)

        source_action = QAction("Source Code Availability...", self)
        source_action.triggered.connect(self._on_show_source)
        license_menu.addAction(source_action)

        help_menu.addSeparator()

        wizard_action = QAction("Setup Wizard...", self)
        wizard_action.triggered.connect(self._on_setup_wizard)
        help_menu.addAction(wizard_action)

        help_menu.addSeparator()

        about_help_action = QAction("About CC Mosquitto...", self)
        about_help_action.triggered.connect(self._on_about)
        help_menu.addAction(about_help_action)

    # =====================================================================
    #  Broker tab
    # =====================================================================

    def _create_broker_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        # -- Status row -------------------------------------------------------
        status_row = QHBoxLayout()
        self._status_indicator = QLabel("\u2B24")
        self._status_indicator.setStyleSheet("color: #E74C3C; font-size: 16px;")
        self._status_label = QLabel("Stopped")
        self._status_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        status_row.addWidget(QLabel("Status:"))
        status_row.addWidget(self._status_indicator)
        status_row.addWidget(self._status_label)
        status_row.addStretch()

        self._start_stop_btn = QPushButton("Start")
        self._start_stop_btn.setFixedWidth(100)
        self._start_stop_btn.clicked.connect(self._on_start_stop)
        status_row.addWidget(self._start_stop_btn)
        layout.addLayout(status_row)

        # -- Network ----------------------------------------------------------
        net_group = QGroupBox("Network")
        net_layout = QVBoxLayout(net_group)

        port_row = QHBoxLayout()
        port_label = QLabel("Port (MQTT):")
        port_label.setToolTip("Network port number for MQTT communication")
        port_row.addWidget(port_label)
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(self._config.port)
        self._port_spin.setToolTip(
            "MQTT port number. Default is 1883.\n"
            "All devices and ChromaChecker Capture stations must use the same port."
        )
        port_row.addWidget(self._port_spin)
        port_row.addStretch()
        net_layout.addLayout(port_row)

        bind_row = QHBoxLayout()
        bind_label = QLabel("Accept connections from:")
        bind_label.setToolTip(
            "Which network interface the broker listens on"
        )
        bind_row.addWidget(bind_label)
        self._bind_edit = QLineEdit(self._config.bind_address)
        self._bind_edit.setFixedWidth(120)
        self._bind_edit.setToolTip(
            "0.0.0.0 = accept from any device in your network (recommended).\n"
            "127.0.0.1 = only this computer (no remote connections)."
        )
        bind_row.addWidget(self._bind_edit)
        bind_row.addStretch()
        net_layout.addLayout(bind_row)

        bind_help = QLabel(
            '<span style="color: #888; font-size: 11px;">'
            "Use <b>0.0.0.0</b> to allow all devices in your network "
            "(recommended). Use <b>127.0.0.1</b> for this computer only."
            "</span>"
        )
        bind_help.setWordWrap(True)
        net_layout.addWidget(bind_help)

        layout.addWidget(net_group)

        # -- Authentication ---------------------------------------------------
        auth_group = QGroupBox("Authentication")
        auth_layout = QVBoxLayout(auth_group)

        self._auth_check = QCheckBox("Require username/password")
        self._auth_check.setChecked(self._config.require_auth)
        self._auth_check.toggled.connect(self._on_auth_toggled)
        self._auth_check.setToolTip(
            "When enabled, every device and application connecting to this\n"
            "broker must provide the username and password configured below.\n\n"
            "Recommended: ON — prevents unauthorized devices from reading\n"
            "your sensor data."
        )
        auth_layout.addWidget(self._auth_check)

        # Help text for authentication
        auth_help = QLabel(
            '<span style="color: #888; font-size: 11px;">'
            "The same username and password must be entered in every "
            "ChromaChecker Capture station (MQTT Broker plugin settings) "
            "and in each sensor's MQTT configuration."
            "</span>"
        )
        auth_help.setWordWrap(True)
        auth_layout.addWidget(auth_help)

        cred_row1 = QHBoxLayout()
        cred_row1.addWidget(QLabel("Username:"))
        self._username_edit = QLineEdit(self._config.username)
        self._username_edit.setToolTip("Username for MQTT authentication.")
        cred_row1.addWidget(self._username_edit)
        auth_layout.addLayout(cred_row1)

        cred_row2 = QHBoxLayout()
        cred_row2.addWidget(QLabel("Password:"))
        self._password_edit = QLineEdit(self._config.password)
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setToolTip("Password for MQTT authentication.")
        cred_row2.addWidget(self._password_edit)
        auth_layout.addLayout(cred_row2)

        self._on_auth_toggled(self._config.require_auth)
        layout.addWidget(auth_group)

        # -- Options ----------------------------------------------------------
        opts_group = QGroupBox("Options")
        opts_layout = QVBoxLayout(opts_group)

        self._autostart_check = QCheckBox("Start on system boot")
        self._autostart_check.setChecked(autostart_mod.is_autostart_enabled())
        self._autostart_check.toggled.connect(self._on_autostart_toggled)
        self._autostart_check.setToolTip(
            "Automatically start CC Mosquitto when you log in.\n"
            "Recommended if you have sensors that send data continuously."
        )
        opts_layout.addWidget(self._autostart_check)

        self._persistence_check = QCheckBox("Enable persistence")
        self._persistence_check.setChecked(self._config.persistence)
        self._persistence_check.setToolTip(
            "Save retained messages to disk so they survive broker restarts.\n"
            "Useful for sensors that publish retained status messages."
        )
        opts_layout.addWidget(self._persistence_check)

        self._logging_check = QCheckBox("Enable logging")
        self._logging_check.setChecked(self._config.logging_enabled)
        self._logging_check.setToolTip("Write broker events to a log file on disk.")
        opts_layout.addWidget(self._logging_check)

        max_row = QHBoxLayout()
        max_row.addWidget(QLabel("Max connections:"))
        self._max_conn_spin = QSpinBox()
        self._max_conn_spin.setRange(1, 10000)
        self._max_conn_spin.setValue(self._config.max_connections)
        self._max_conn_spin.setToolTip(
            "Maximum number of simultaneous MQTT client connections.\n"
            "100 is sufficient for most setups."
        )
        max_row.addWidget(self._max_conn_spin)
        max_row.addStretch()
        opts_layout.addLayout(max_row)

        layout.addWidget(opts_group)
        layout.addStretch()

        return tab

    # =====================================================================
    #  Network Guide tab
    # =====================================================================

    def _create_network_guide_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(self._network_guide_html())
        content_layout.addWidget(browser)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        return tab

    def _network_guide_html(self) -> str:
        ips = _get_local_ips()
        ip_list = ", ".join(f"<b>{ip}</b>" for ip in ips)
        port = self._config.port
        username = self._config.username or "capture"

        return f"""
        <h2>Network Setup Guide</h2>

        <h3>Your Broker Address</h3>
        <p>This computer's IP address: {ip_list}<br>
        Port: <b>{port}</b></p>

        <p style="background: #2a4a2a; padding: 10px; border-radius: 4px;">
        <b>Broker address for all devices:</b><br>
        <code style="font-size: 14px;">{ips[0] if ips else '?'}:{port}</code>
        </p>

        <hr>

        <h3>Typical Setup: Multiple Capture Stations</h3>
        <p>In a typical production environment, you have several computers
        running ChromaChecker Capture and one running CC Mosquitto:</p>

        <table cellpadding="0" cellspacing="0" style="margin: 8px auto; font-size: 12px;">
        <tr>
            <td style="background: #1a3a1a; border: 2px solid #27AE60; border-radius: 8px;
                        padding: 12px 16px; vertical-align: middle; text-align: center;"
                rowspan="3">
                <b>This Computer</b><br>
                <span style="color: #27AE60;">CC Mosquitto</span><br>
                (MQTT Broker)<br><br>
                <code>{ips[0] if ips else '?'}:{port}</code>
            </td>
            <td style="padding: 8px; color: #3498DB; font-size: 18px; text-align: center;">
                ◄────
            </td>
            <td style="background: #1a2a3a; border: 1px solid #3498DB; border-radius: 6px;
                        padding: 8px 12px; text-align: center;">
                <b>Capture Station 1</b><br>
                <span style="color: #888;">MQTT Broker plugin</span><br>
                <code>{ips[0] if ips else '?'}:{port}</code>
            </td>
        </tr>
        <tr>
            <td style="padding: 8px; color: #3498DB; font-size: 18px; text-align: center;">
                ◄────
            </td>
            <td style="background: #1a2a3a; border: 1px solid #3498DB; border-radius: 6px;
                        padding: 8px 12px; text-align: center;">
                <b>Capture Station 2</b><br>
                <span style="color: #888;">MQTT Broker plugin</span><br>
                <code>{ips[0] if ips else '?'}:{port}</code>
            </td>
        </tr>
        <tr>
            <td style="padding: 8px; color: #E67E22; font-size: 18px; text-align: center;">
                ◄────
            </td>
            <td style="background: #2a2a1a; border: 1px solid #E67E22; border-radius: 6px;
                        padding: 8px 12px; text-align: center;">
                <b>Shelly H&amp;T</b><br>
                <span style="color: #888;">WiFi sensor</span><br>
                <code>MQTT: {ips[0] if ips else '?'}:{port}</code>
            </td>
        </tr>
        </table>

        <hr>

        <h3>Step-by-Step Setup</h3>

        <h4>1. Configure ChromaChecker Capture stations</h4>
        <p>On <b>each</b> computer running ChromaChecker Capture:</p>
        <ol>
            <li>Open <b>Device &rarr; MQTT Broker</b> (or Plugin Manager &rarr; MQTT Broker &rarr; Setup)</li>
            <li>Enter the broker address: <code>{ips[0] if ips else '?'}</code></li>
            <li>Enter port: <code>{port}</code></li>
            <li>Enter username: <code>{username}</code></li>
            <li>Enter the password configured above</li>
            <li>Click <b>Test Connection</b> to verify</li>
            <li>Click <b>Save</b></li>
        </ol>

        <h4>2. Configure WiFi sensors (Shelly, Tasmota)</h4>
        <p>In your sensor's web interface:</p>
        <ol>
            <li>Find the MQTT settings page</li>
            <li>Set broker/server to: <code>{ips[0] if ips else '?'}</code></li>
            <li>Set port to: <code>{port}</code></li>
            <li>Enter the same username and password</li>
            <li>Save and restart the sensor</li>
        </ol>
        <p><b>Shelly:</b> Settings &rarr; MQTT &rarr; Enable MQTT &rarr; enter broker IP<br>
        <b>Tasmota:</b> Configuration &rarr; MQTT &rarr; Host = broker IP</p>

        <h4>3. Configure Zigbee sensors (via Zigbee2MQTT)</h4>
        <p>If you use Zigbee sensors with Zigbee2MQTT:</p>
        <ol>
            <li>Edit <code>configuration.yaml</code> in Zigbee2MQTT</li>
            <li>Set <code>mqtt.server</code> to: <code>mqtt://{ips[0] if ips else '?'}:{port}</code></li>
            <li>Set <code>mqtt.user</code> and <code>mqtt.password</code></li>
            <li>Restart Zigbee2MQTT</li>
        </ol>

        <hr>

        <h3>Troubleshooting</h3>
        <table cellpadding="6" width="100%">
        <tr>
            <td style="color: #E74C3C;"><b>Connection refused</b></td>
            <td>Check that CC Mosquitto is running (green status).
            Check that the firewall allows port {port}.</td>
        </tr>
        <tr>
            <td style="color: #E74C3C;"><b>Not authorised</b></td>
            <td>Wrong username or password. Make sure you use the exact
            same credentials as configured in CC Mosquitto.</td>
        </tr>
        <tr>
            <td style="color: #E74C3C;"><b>Cannot find broker</b></td>
            <td>Ensure all devices are on the same network (same WiFi/LAN).
            Try pinging this computer's IP from the other station.</td>
        </tr>
        <tr>
            <td style="color: #E74C3C;"><b>Sensor data not arriving</b></td>
            <td>Check the Connection Log tab — you should see the sensor
            connect. If it connects but no data appears in Capture, check
            the MQTT topic in the RHT sensor settings.</td>
        </tr>
        </table>

        <hr>

        <h3>About Credentials</h3>
        <p>The <b>username</b> and <b>password</b> protect your broker from
        unauthorized access. Without authentication, anyone on your network
        could read sensor data or send commands to your devices.</p>

        <p><b>Where to enter these credentials:</b></p>
        <ul>
            <li>Here in CC Mosquitto — defines the allowed credentials</li>
            <li>In each ChromaChecker Capture — MQTT Broker plugin settings</li>
            <li>In each sensor — MQTT configuration page</li>
        </ul>
        <p>All must use the <b>same</b> username and password.</p>
        """

    # =====================================================================
    #  Slots
    # =====================================================================

    @Slot()
    def _on_start_stop(self) -> None:
        if self._manager.is_running():
            self._manager.stop()
        else:
            self._apply_config()
            self._manager.start()

    @Slot()
    def _on_broker_started(self) -> None:
        self._status_indicator.setStyleSheet("color: #27AE60; font-size: 16px;")
        self._status_label.setText("Running")
        self._start_stop_btn.setText("Stop")
        self._set_controls_enabled(False)
        self._status_bar_label.setText(
            f"Broker running on port {self._config.port}"
        )

    @Slot()
    def _on_broker_stopped(self) -> None:
        self._status_indicator.setStyleSheet("color: #E74C3C; font-size: 16px;")
        self._status_label.setText("Stopped")
        self._start_stop_btn.setText("Start")
        self._set_controls_enabled(True)
        self._clients_label.setText("Clients: 0")
        self._status_bar_label.setText("")

    @Slot(str)
    def _on_broker_error(self, msg: str) -> None:
        self._log_viewer.append_line(f"ERROR: {msg}")

    @Slot(bool)
    def _on_auth_toggled(self, checked: bool) -> None:
        self._username_edit.setEnabled(checked)
        self._password_edit.setEnabled(checked)

    @Slot(bool)
    def _on_autostart_toggled(self, checked: bool) -> None:
        if checked:
            autostart_mod.enable_autostart()
        else:
            autostart_mod.disable_autostart()

    @Slot(int)
    def _on_client_count(self, count: int) -> None:
        self._clients_label.setText(f"Clients: {count}")

    # -- Menu handlers --------------------------------------------------------

    def _on_about(self) -> None:
        from .about_dialog import AboutDialog
        dlg = AboutDialog(self)
        dlg.exec()

    def _on_setup_wizard(self) -> None:
        from .setup_wizard import SetupWizard
        wizard = SetupWizard(self._config, parent=self)

        def _apply(new_config: BrokerConfig):
            self.reload_config(new_config)
            self._manager.config = new_config
            if wizard.start_broker_now and not self._manager.is_running():
                self._manager.start()

        wizard.finished_config.connect(_apply)
        wizard.exec()

    def _on_show_epl(self) -> None:
        QMessageBox.information(
            self,
            "Eclipse Public License 2.0",
            "CC Mosquitto includes Eclipse Mosquitto, which is licensed "
            "under the Eclipse Public License 2.0 (EPL-2.0).\n\n"
            "Full license text:\n"
            "https://www.eclipse.org/legal/epl-2.0/\n\n"
            "Source code:\n"
            "https://github.com/eclipse/mosquitto",
        )

    def _on_show_third_party(self) -> None:
        from .about_dialog import AboutDialog
        dlg = AboutDialog(self)
        # Switch to Third-Party tab
        for i in range(dlg.findChildren(QTabWidget)[0].count()):
            tw = dlg.findChildren(QTabWidget)[0]
            if "third" in tw.tabText(i).lower():
                tw.setCurrentIndex(i)
                break
        dlg.exec()

    def _on_show_source(self) -> None:
        QMessageBox.information(
            self,
            "Source Code Availability",
            "As required by the Eclipse Public License 2.0, the source "
            "code for the Mosquitto component is available at:\n\n"
            "https://github.com/eclipse/mosquitto\n\n"
            "Any modifications made by ChromaChecker are available at:\n"
            "https://github.com/ChromaChecker/cc-mosquitto",
        )

    # -- Helpers --------------------------------------------------------------

    def _apply_config(self) -> None:
        self._config.port = self._port_spin.value()
        self._config.bind_address = self._bind_edit.text().strip() or "0.0.0.0"
        self._config.require_auth = self._auth_check.isChecked()
        self._config.username = self._username_edit.text().strip()
        self._config.password = self._password_edit.text()
        self._config.persistence = self._persistence_check.isChecked()
        self._config.logging_enabled = self._logging_check.isChecked()
        self._config.max_connections = self._max_conn_spin.value()
        self._config.autostart = self._autostart_check.isChecked()
        self._config.save()
        self._manager.config = self._config

    def _set_controls_enabled(self, enabled: bool) -> None:
        self._port_spin.setEnabled(enabled)
        self._bind_edit.setEnabled(enabled)
        self._auth_check.setEnabled(enabled)
        if enabled:
            self._on_auth_toggled(self._auth_check.isChecked())
        else:
            self._username_edit.setEnabled(False)
            self._password_edit.setEnabled(False)
        self._persistence_check.setEnabled(enabled)
        self._logging_check.setEnabled(enabled)
        self._max_conn_spin.setEnabled(enabled)

    def reload_config(self, config: BrokerConfig) -> None:
        """Update all UI controls to reflect a new config (e.g. from wizard)."""
        self._config = config
        self._port_spin.setValue(config.port)
        self._bind_edit.setText(config.bind_address)
        self._auth_check.setChecked(config.require_auth)
        self._username_edit.setText(config.username)
        self._password_edit.setText(config.password)
        self._persistence_check.setChecked(config.persistence)
        self._logging_check.setChecked(config.logging_enabled)
        self._max_conn_spin.setValue(config.max_connections)
        self._autostart_check.setChecked(config.autostart)

    # -- Window events --------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        self.hide()
        # Show tray notification on first minimize so user knows it's still running
        from PySide6.QtWidgets import QSystemTrayIcon
        tray = self.findChild(QSystemTrayIcon)
        if tray is None:
            # Find tray from app-level — notify via parent chain
            for widget in QApplication.instance().findChildren(QSystemTrayIcon):
                tray = widget
                break
        if tray and tray.isVisible() and self._manager.is_running():
            tray.showMessage(
                "CC Mosquitto",
                "The broker is still running in the background.\n"
                "Click the tray icon to open the window.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )

    def confirm_quit(self) -> bool:
        if not self._manager.is_running():
            return True
        msg = QMessageBox(self)
        msg.setWindowTitle("Quit CC Mosquitto")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText("The MQTT broker is still running.")
        msg.setInformativeText(
            "Quitting will stop the broker and disconnect all devices.\n\n"
            "All sensors and ChromaChecker Capture stations that rely on "
            "this broker will lose their MQTT connection until the broker "
            "is restarted.\n\n"
            "To keep the broker running in the background, close this "
            "window instead — it will minimize to the system tray."
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.button(QMessageBox.StandardButton.Yes).setText("Stop Broker && Quit")
        msg.button(QMessageBox.StandardButton.No).setText("Cancel")
        return msg.exec() == QMessageBox.StandardButton.Yes
