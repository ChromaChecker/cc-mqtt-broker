"""Mosquitto subprocess lifecycle manager.

Generates ``mosquitto.conf``, starts/stops the Mosquitto binary via
QProcess, and streams log output to the GUI.
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from .config import BrokerConfig

logger = logging.getLogger(__name__)


def _find_mosquitto_binary() -> Path | None:
    """Locate the Mosquitto binary.

    Search order:
    1. Bundled inside the app (PyInstaller / .app bundle)
    2. System PATH (Homebrew, package manager, etc.)
    """
    # 1. Bundled
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent.parent
    for candidate in (
        base / "mosquitto",
        base / "Resources" / "mosquitto",
        base / "mosquitto.exe",
    ):
        if candidate.is_file():
            return candidate

    # 2. System PATH
    found = shutil.which("mosquitto")
    if found:
        return Path(found)

    return None


def _find_mosquitto_passwd() -> Path | None:
    """Locate the mosquitto_passwd utility."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent.parent
    for candidate in (
        base / "mosquitto_passwd",
        base / "Resources" / "mosquitto_passwd",
        base / "mosquitto_passwd.exe",
    ):
        if candidate.is_file():
            return candidate

    found = shutil.which("mosquitto_passwd")
    if found:
        return Path(found)

    return None


class BrokerManager(QObject):
    """Manages the Mosquitto broker process.

    Signals:
        started: Broker process started successfully.
        stopped: Broker process stopped.
        error_occurred: Error message string.
        log_line_received: One line of broker log output.
    """

    started = Signal()
    stopped = Signal()
    error_occurred = Signal(str)
    log_line_received = Signal(str)

    def __init__(self, config: BrokerConfig, parent: QObject | None = None):
        super().__init__(parent)
        self._config = config
        self._process: QProcess | None = None
        self._mosquitto_bin = _find_mosquitto_binary()
        self._mosquitto_passwd_bin = _find_mosquitto_passwd()

    # -- Properties -----------------------------------------------------------

    @property
    def config(self) -> BrokerConfig:
        return self._config

    @config.setter
    def config(self, value: BrokerConfig) -> None:
        self._config = value

    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() == QProcess.ProcessState.Running
        )

    # -- Lifecycle ------------------------------------------------------------

    def start(self) -> bool:
        """Generate config and start the Mosquitto process.

        Returns True if the process started successfully.
        """
        if self.is_running():
            logger.warning("Broker already running")
            return True

        if self._mosquitto_bin is None:
            msg = "Mosquitto binary not found"
            logger.error(msg)
            self.error_occurred.emit(msg)
            return False

        # Ensure runtime directories exist
        self._config.base_dir.mkdir(parents=True, exist_ok=True)
        self._config.data_dir.mkdir(parents=True, exist_ok=True)
        self._config.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate password file if auth is required
        if self._config.require_auth:
            if not self._generate_passwd_file():
                return False

        # Generate mosquitto.conf
        conf_path = self._generate_config()

        # Start process
        self._process = QProcess(self)
        self._process.setProgram(str(self._mosquitto_bin))
        self._process.setArguments(["-c", str(conf_path), "-v"])
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)

        self._process.start()
        if not self._process.waitForStarted(5000):
            msg = f"Failed to start Mosquitto: {self._process.errorString()}"
            logger.error(msg)
            self.error_occurred.emit(msg)
            return False

        logger.info(
            "Mosquitto started (PID %d) on port %d",
            self._process.processId(),
            self._config.port,
        )
        self.started.emit()
        return True

    def stop(self) -> None:
        """Stop the Mosquitto process gracefully."""
        if not self.is_running():
            return
        logger.info("Stopping Mosquitto...")
        self._process.terminate()
        if not self._process.waitForFinished(5000):
            logger.warning("Mosquitto did not stop in 5 s — killing")
            self._process.kill()
            self._process.waitForFinished(3000)

    def restart(self) -> bool:
        """Stop and re-start with current config."""
        self.stop()
        return self.start()

    # -- User management ------------------------------------------------------

    def add_user(self, username: str, password: str) -> bool:
        """Add or update a user in the password file."""
        if self._mosquitto_passwd_bin is None:
            self.error_occurred.emit("mosquitto_passwd utility not found")
            return False

        passwd_path = self._config.passwd_path
        # -b = batch mode (password on command line)
        # -c = create file if first user
        args = ["-b"]
        if not passwd_path.is_file():
            args.append("-c")
        args.extend([str(passwd_path), username, password])

        try:
            result = subprocess.run(
                [str(self._mosquitto_passwd_bin)] + args,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                msg = f"mosquitto_passwd failed: {result.stderr.strip()}"
                logger.error(msg)
                self.error_occurred.emit(msg)
                return False
            logger.info("User '%s' added/updated in password file", username)
            return True
        except Exception as exc:
            msg = f"mosquitto_passwd error: {exc}"
            logger.error(msg)
            self.error_occurred.emit(msg)
            return False

    def remove_user(self, username: str) -> bool:
        """Remove a user from the password file."""
        if self._mosquitto_passwd_bin is None:
            self.error_occurred.emit("mosquitto_passwd utility not found")
            return False

        passwd_path = self._config.passwd_path
        if not passwd_path.is_file():
            return True  # No file = nothing to remove

        try:
            result = subprocess.run(
                [str(self._mosquitto_passwd_bin), "-D", str(passwd_path), username],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                msg = f"mosquitto_passwd -D failed: {result.stderr.strip()}"
                logger.error(msg)
                self.error_occurred.emit(msg)
                return False
            logger.info("User '%s' removed from password file", username)
            return True
        except Exception as exc:
            msg = f"mosquitto_passwd error: {exc}"
            logger.error(msg)
            self.error_occurred.emit(msg)
            return False

    # -- Config generation ----------------------------------------------------

    def _generate_config(self) -> Path:
        """Write ``mosquitto.conf`` from current BrokerConfig."""
        c = self._config
        lines = [
            "# Generated by CC Mosquitto — do not edit manually",
            f"listener {c.port} {c.bind_address}",
            "protocol mqtt",
            "",
        ]

        # Authentication
        if c.require_auth:
            lines.append("allow_anonymous false")
            lines.append(f"password_file {c.passwd_path}")
        else:
            lines.append("allow_anonymous true")
        lines.append("")

        # Persistence
        if c.persistence:
            lines.append("persistence true")
            lines.append(f"persistence_location {c.data_dir}/")
        else:
            lines.append("persistence false")
        lines.append("")

        # Logging
        if c.logging_enabled:
            lines.append(f"log_dest file {c.log_path}")
            lines.append("log_dest stderr")
        else:
            lines.append("log_dest stderr")
        lines.extend([
            "log_type warning",
            "log_type error",
            "log_type notice",
            "log_type information",
            "connection_messages true",
            "",
        ])

        # Limits
        lines.append(f"max_connections {c.max_connections}")
        lines.append("")

        c.config_path.write_text("\n".join(lines), encoding="utf-8")
        logger.debug("Generated %s", c.config_path)
        return c.config_path

    def _generate_passwd_file(self) -> bool:
        """Ensure the password file exists with the configured user."""
        if not self._config.username or not self._config.password:
            self.error_occurred.emit(
                "Authentication is enabled but username/password is empty"
            )
            return False
        return self.add_user(self._config.username, self._config.password)

    # -- QProcess callbacks ---------------------------------------------------

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            line = line.strip()
            if line:
                self.log_line_received.emit(line)

    def _on_stderr(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardError().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            line = line.strip()
            if line:
                self.log_line_received.emit(line)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        logger.info(
            "Mosquitto exited (code=%d, status=%s)", exit_code, exit_status.name
        )
        self.stopped.emit()
        if exit_status == QProcess.ExitStatus.CrashExit:
            self.error_occurred.emit(
                f"Mosquitto crashed (exit code {exit_code})"
            )
