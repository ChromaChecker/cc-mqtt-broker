"""CC Mosquitto application entry point.

Usage:
    python -m cc_mosquitto
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from .broker_manager import BrokerManager
from .config import BrokerConfig
from .main_window import MainWindow
from .setup_wizard import SetupWizard
from .tray_icon import TrayIcon

logger = logging.getLogger(__name__)


def main() -> int:
    """Launch the CC Mosquitto GUI application."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    app = QApplication(sys.argv)
    app.setApplicationName("CC Mosquitto")
    app.setOrganizationName("ChromaChecker")
    app.setOrganizationDomain("chromachecker.com")
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray

    # Load saved configuration
    config = BrokerConfig.load()
    manager = BrokerManager(config)

    # Main window
    window = MainWindow(manager)

    # System tray
    tray = TrayIcon()
    tray.start_requested.connect(lambda: (window._apply_config(), manager.start()))
    tray.stop_requested.connect(manager.stop)
    tray.show_requested.connect(window.show)
    tray.show_requested.connect(window.raise_)

    def _on_quit():
        if window.confirm_quit():
            manager.stop()
            app.quit()

    tray.quit_requested.connect(_on_quit)

    # Sync tray icon with broker state
    manager.started.connect(lambda: tray.set_running(True))
    manager.stopped.connect(lambda: tray.set_running(False))

    # Show tray and window
    tray.show()
    window.show()

    # First-run setup wizard
    settings = QSettings("ChromaChecker", "CCMosquitto")
    if not settings.value("wizard/completed", False):
        _run_first_time_wizard(window, manager, config, settings)
    elif config.autostart:
        logger.info("Auto-starting broker (autostart=True)")
        manager.start()

    return app.exec()


def _run_first_time_wizard(
    window: MainWindow,
    manager: BrokerManager,
    config: BrokerConfig,
    settings: QSettings,
) -> None:
    """Show the setup wizard on first launch."""
    wizard = SetupWizard(config, parent=window)

    def _on_wizard_done(new_config: BrokerConfig):
        # Update manager with wizard config
        manager.config = new_config
        window.reload_config(new_config)
        settings.setValue("wizard/completed", True)
        settings.sync()
        logger.info("Setup wizard completed")
        if wizard.start_broker_now:
            manager.start()

    wizard.finished_config.connect(_on_wizard_done)

    # If user skips wizard, still mark as seen so it doesn't reappear
    def _on_rejected():
        settings.setValue("wizard/completed", True)
        settings.sync()
        logger.info("Setup wizard skipped")

    wizard.rejected.connect(_on_rejected)
    wizard.exec()


if __name__ == "__main__":
    sys.exit(main())
