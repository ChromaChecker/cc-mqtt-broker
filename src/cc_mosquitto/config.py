"""Broker configuration dataclass and persistence."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QSettings

logger = logging.getLogger(__name__)

# Default runtime directory
_DEFAULT_DIR = Path.home() / ".cc_mosquitto"


@dataclass
class BrokerConfig:
    """Mosquitto broker runtime configuration.

    All fields are persisted to QSettings so the GUI can restore
    its state on next launch.
    """

    port: int = 1883
    bind_address: str = "0.0.0.0"
    require_auth: bool = True
    username: str = "capture"
    password: str = ""
    persistence: bool = True
    logging_enabled: bool = True
    max_connections: int = 100
    autostart: bool = False

    # Derived paths (not persisted — computed from base_dir)
    base_dir: Path = field(default_factory=lambda: _DEFAULT_DIR)

    @property
    def config_path(self) -> Path:
        return self.base_dir / "mosquitto.conf"

    @property
    def passwd_path(self) -> Path:
        return self.base_dir / "passwd"

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def log_path(self) -> Path:
        return self.base_dir / "log" / "mosquitto.log"

    # -- Persistence ----------------------------------------------------------

    def save(self) -> None:
        """Persist configuration to QSettings."""
        s = QSettings("ChromaChecker", "CCMosquitto")
        s.setValue("broker/port", self.port)
        s.setValue("broker/bind_address", self.bind_address)
        s.setValue("broker/require_auth", self.require_auth)
        s.setValue("broker/username", self.username)
        # Password is stored here for simplicity — CC Mosquitto is a
        # local-only utility; the password protects the broker, not a
        # cloud account.  For true secrets use keyring.
        s.setValue("broker/password", self.password)
        s.setValue("broker/persistence", self.persistence)
        s.setValue("broker/logging_enabled", self.logging_enabled)
        s.setValue("broker/max_connections", self.max_connections)
        s.setValue("broker/autostart", self.autostart)
        s.sync()
        logger.debug("BrokerConfig saved")

    @classmethod
    def load(cls) -> BrokerConfig:
        """Load configuration from QSettings, falling back to defaults."""
        s = QSettings("ChromaChecker", "CCMosquitto")
        cfg = cls()
        cfg.port = int(s.value("broker/port", cfg.port))
        cfg.bind_address = str(s.value("broker/bind_address", cfg.bind_address))
        cfg.require_auth = _to_bool(s.value("broker/require_auth", cfg.require_auth))
        cfg.username = str(s.value("broker/username", cfg.username))
        cfg.password = str(s.value("broker/password", cfg.password))
        cfg.persistence = _to_bool(s.value("broker/persistence", cfg.persistence))
        cfg.logging_enabled = _to_bool(s.value("broker/logging_enabled", cfg.logging_enabled))
        cfg.max_connections = int(s.value("broker/max_connections", cfg.max_connections))
        cfg.autostart = _to_bool(s.value("broker/autostart", cfg.autostart))
        return cfg


def _to_bool(value: object) -> bool:
    """Convert QSettings value to bool (handles string 'true'/'false')."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)
