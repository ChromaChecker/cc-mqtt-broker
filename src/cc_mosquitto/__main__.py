"""Allow running CC Mosquitto with: python -m cc_mosquitto"""

import sys

try:
    from .app import main
except ImportError:
    # PyInstaller frozen mode — relative imports don't work
    from cc_mosquitto.app import main

sys.exit(main())
