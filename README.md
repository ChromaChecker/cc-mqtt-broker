# CC Mosquitto

Standalone MQTT broker with a graphical user interface, built on Eclipse Mosquitto.

Designed as a companion tool for ChromaChecker Capture's IoT integrations
(RHT sensors, Signal Tower), but works as a general-purpose MQTT broker.

## Features

- Simple GUI for starting/stopping the broker
- System tray integration (runs in background)
- Username/password authentication
- Auto-start on system boot (macOS LaunchAgent, Windows Registry)
- Live connection log with colour-coded output
- Persistence for retained messages

## Requirements

- Python 3.11+
- PySide6
- Mosquitto binary (installed via Homebrew or built from source)

## Running (development)

```bash
cd src
python -m cc_mosquitto
```

## License

- Mosquitto broker: EPL-2.0 (Eclipse Public License 2.0)
- GUI wrapper: Proprietary (ChromaChecker)

See `LICENSE_EPL2.txt` and `SOURCE_CODE.txt` for details.
