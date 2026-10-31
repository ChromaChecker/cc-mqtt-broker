# CC MQTT Broker

CC MQTT Broker (formerly CC Mosquitto) is ChromaChecker's desktop MQTT
broker for macOS and Windows. It runs Eclipse Mosquitto behind a graphical
user interface. It is designed as a companion to ChromaChecker Capture's
IoT integrations (RHT sensors, Signal Tower) and also works as a
general-purpose MQTT broker.

## Eclipse Mosquitto (EPL-2.0)

CC MQTT Broker includes Eclipse Mosquitto 2.1.2, licensed under the
Eclipse Public License 2.0:

- macOS: the Homebrew build of Mosquitto
- Windows: the binaries from the official Eclipse Mosquitto installer,
  re-signed by ChromaChecker Corporation

ChromaChecker has not modified the Mosquitto source code. The complete
source is available at https://github.com/eclipse-mosquitto/mosquitto
(tag v2.1.2).

## License

- Eclipse Mosquitto: EPL-2.0 (see LICENSE_EPL2.txt)
- CC MQTT Broker graphical user interface: proprietary,
  © ChromaChecker Corporation
