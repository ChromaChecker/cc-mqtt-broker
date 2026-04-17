# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CC Mosquitto.

Bundles:
- cc_mosquitto Python package (GUI)
- mosquitto binary + mosquitto_passwd
- Required dylibs (OpenSSL, cJSON)
- Translation JSON files
- License texts
"""
import os
import re
import shutil

# Spec file lives in build/ — project root is one level up
PROJECT_ROOT = os.path.dirname(SPECPATH)

# Read version from __init__.py
_version_file = os.path.join(PROJECT_ROOT, 'src', 'cc_mosquitto', '__init__.py')
with open(_version_file) as _f:
    _match = re.search(r'__version__\s*=\s*"([^"]+)"', _f.read())
    APP_VERSION = _match.group(1) if _match else '1.0.0'

# Mosquitto binaries (Homebrew ARM)
MOSQUITTO_BIN = shutil.which('mosquitto') or '/opt/homebrew/sbin/mosquitto'
MOSQUITTO_PASSWD = shutil.which('mosquitto_passwd') or '/opt/homebrew/bin/mosquitto_passwd'

# Dylibs that mosquitto needs at runtime
HOMEBREW_LIB = '/opt/homebrew/lib'
HOMEBREW_OPT = '/opt/homebrew/opt'
_dylibs = [
    (os.path.join(HOMEBREW_OPT, 'openssl@3/lib/libssl.3.dylib'), '.'),
    (os.path.join(HOMEBREW_OPT, 'openssl@3/lib/libcrypto.3.dylib'), '.'),
    (os.path.join(HOMEBREW_OPT, 'cjson/lib/libcjson.1.dylib'), '.'),
]

# Translation files
_translations_dir = os.path.join(PROJECT_ROOT, 'src', 'cc_mosquitto', 'translations')
_translation_datas = []
if os.path.isdir(_translations_dir):
    for f in os.listdir(_translations_dir):
        fp = os.path.join(_translations_dir, f)
        if f.endswith('.json'):
            _translation_datas.append((fp, 'cc_mosquitto/translations'))
        elif os.path.isdir(fp):
            # template/ subdirectory
            for sf in os.listdir(fp):
                if sf.endswith('.json'):
                    _translation_datas.append(
                        (os.path.join(fp, sf), f'cc_mosquitto/translations/{f}')
                    )

# License files
_license_datas = [
    (os.path.join(PROJECT_ROOT, 'LICENSE_EPL2.txt'), '.'),
    (os.path.join(PROJECT_ROOT, 'SOURCE_CODE.txt'), '.'),
]

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'src', 'cc_mosquitto', '__main__.py')],
    pathex=[os.path.join(PROJECT_ROOT, 'src')],
    binaries=[
        (MOSQUITTO_BIN, '.'),
        (MOSQUITTO_PASSWD, '.'),
    ] + _dylibs,
    datas=_translation_datas + _license_datas,
    hiddenimports=[
        'cc_mosquitto',
        'cc_mosquitto.app',
        'cc_mosquitto.config',
        'cc_mosquitto.broker_manager',
        'cc_mosquitto.main_window',
        'cc_mosquitto.log_viewer',
        'cc_mosquitto.tray_icon',
        'cc_mosquitto.autostart',
        'cc_mosquitto.about_dialog',
        'cc_mosquitto.setup_wizard',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'test', 'unittest',
        'matplotlib', 'numpy', 'scipy', 'pandas',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CC Mosquitto',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='CC Mosquitto',
)

app = BUNDLE(
    coll,
    name=f'CC Mosquitto {APP_VERSION}.app',
    icon=os.path.join(SPECPATH, 'CC_Mosquitto.icns')
         if os.path.exists(os.path.join(SPECPATH, 'CC_Mosquitto.icns'))
         else None,
    bundle_identifier='com.chromachecker.ccmosquitto',
    info_plist={
        'CFBundleName': 'CC Mosquitto',
        'CFBundleDisplayName': 'CC Mosquitto',
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleVersion': APP_VERSION,
        'LSMinimumSystemVersion': '12.0',
        'NSHighResolutionCapable': True,
        'LSUIElement': False,
        'NSHumanReadableCopyright':
            f'© 2026 ChromaChecker / Art-Fab Krzysztof Szafraniec. '
            f'Mosquitto © Eclipse Foundation (EPL-2.0).',
    },
)
