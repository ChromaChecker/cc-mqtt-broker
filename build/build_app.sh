#!/bin/bash
# Build script for CC Mosquitto (macOS)
# Runs PyInstaller, signs, and packages as DMG.
#
# Output: CC Mosquitto <VERSION>m arm.dmg
#
# Usage: ./build_app.sh
#
# Environment flags:
#   SKIP_SIGN=true      Skip code signing
#   SKIP_NOTARIZE=true  Skip notarization (still signs)
#   SKIP_DMG=true       Skip DMG creation

set -e

# ── Paths ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

APP_NAME="CC Mosquitto"
RAW_ARCH="$(uname -m)"
case "$RAW_ARCH" in
    arm64)  ARCH="arm"; PLATFORM_SUFFIX="m" ;;
    x86_64) ARCH="Intel"; PLATFORM_SUFFIX="i" ;;
    *)      ARCH="$RAW_ARCH"; PLATFORM_SUFFIX="" ;;
esac

# ── Signing & Notarization ───────────────────────────────────────────────
SIGN_IDENTITY="Developer ID Application: ChromaChecker Corporation (7385NZX7E8)"
TEAM_ID="7385NZX7E8"
ENTITLEMENTS="${SCRIPT_DIR}/entitlements.plist"
NOTARIZE_PROFILE="CC-Notarize"

SKIP_SIGN="${SKIP_SIGN:-false}"
SKIP_NOTARIZE="${SKIP_NOTARIZE:-false}"
SKIP_DMG="${SKIP_DMG:-false}"

# ── Version ──────────────────────────────────────────────────────────────
VERSION_FILE="${PROJECT_DIR}/src/cc_mosquitto/__init__.py"
RAW_VERSION=$(sed -n 's/.*__version__ *= *"\([^"]*\)".*/\1/p' "${VERSION_FILE}")
if [ -z "${RAW_VERSION}" ]; then
    echo "ERROR: Could not parse __version__ from ${VERSION_FILE}"
    exit 1
fi
APP_VERSION="${RAW_VERSION}${PLATFORM_SUFFIX}"

# ── Build directory (local disk) ─────────────────────────────────────────
LOCAL_BUILD_DIR="/tmp/cc-mosquitto-build"
LOCAL_DIST="${LOCAL_BUILD_DIR}/dist"
LOCAL_WORK="${LOCAL_BUILD_DIR}/build_output"

# ── DMG destination ──────────────────────────────────────────────────────
DMG_DIR="${PROJECT_DIR}/DMG_Releases"
mkdir -p "${DMG_DIR}"

TOTAL_STEPS=5

echo "=========================================="
echo "Building ${APP_NAME} ${APP_VERSION} ${ARCH}"
echo "  Version:    ${APP_VERSION}"
echo "  Platform:   macOS $(sw_vers -productVersion 2>/dev/null || echo 'unknown') ${ARCH}"
echo "  Python:     $(python3 --version 2>&1)"
echo "  Project:    ${PROJECT_DIR}"
echo "  Temp dir:   ${LOCAL_BUILD_DIR}"
echo "  Sign:       $([ "$SKIP_SIGN" = "true" ] && echo "SKIP" || echo "YES")"
echo "  Notarize:   $([ "$SKIP_NOTARIZE" = "true" ] && echo "SKIP" || echo "YES")"
echo "  DMG:        $([ "$SKIP_DMG" = "true" ] && echo "SKIP" || echo "YES")"
echo "=========================================="

# ── Step 1: PyInstaller ──────────────────────────────────────────────────
echo ""
echo "[1/${TOTAL_STEPS}] Running PyInstaller..."
mkdir -p "${LOCAL_DIST}" "${LOCAL_WORK}"

cd "${PROJECT_DIR}"
pyinstaller "build/CC_Mosquitto.spec" \
    --noconfirm \
    --distpath "${LOCAL_DIST}" \
    --workpath "${LOCAL_WORK}"

# PyInstaller uses the raw version from __init__.py (no platform suffix).
# Find the .app it created and rename to include platform suffix.
PYINSTALLER_APP="${LOCAL_DIST}/${APP_NAME} ${RAW_VERSION}.app"
APP_PATH="${LOCAL_DIST}/${APP_NAME} ${APP_VERSION}.app"

if [ ! -d "${PYINSTALLER_APP}" ]; then
    echo "ERROR: PyInstaller did not produce expected .app"
    ls -la "${LOCAL_DIST}/"
    exit 1
fi

if [ "${PYINSTALLER_APP}" != "${APP_PATH}" ]; then
    rm -rf "${APP_PATH}"
    mv "${PYINSTALLER_APP}" "${APP_PATH}"
    echo "      Renamed to include platform suffix: ${APP_VERSION}"
fi
echo "      .app built: ${APP_PATH}"

# ── Step 2: Fix dylib paths in mosquitto binaries ────────────────────────
echo ""
echo "[2/${TOTAL_STEPS}] Fixing dylib paths..."
FRAMEWORKS_DIR="${APP_PATH}/Contents/Frameworks"

# mosquitto and mosquitto_passwd are in Frameworks/ (PyInstaller puts binaries there).
# Rewrite their Homebrew dylib paths to @loader_path (same directory).
for BINARY in "${FRAMEWORKS_DIR}/mosquitto" "${FRAMEWORKS_DIR}/mosquitto_passwd"; do
    if [ -f "$BINARY" ]; then
        install_name_tool -change \
            /opt/homebrew/opt/openssl@3/lib/libssl.3.dylib \
            @loader_path/libssl.3.dylib \
            "$BINARY" 2>/dev/null || true
        install_name_tool -change \
            /opt/homebrew/opt/openssl@3/lib/libcrypto.3.dylib \
            @loader_path/libcrypto.3.dylib \
            "$BINARY" 2>/dev/null || true
        install_name_tool -change \
            /opt/homebrew/opt/cjson/lib/libcjson.1.dylib \
            @loader_path/libcjson.1.dylib \
            "$BINARY" 2>/dev/null || true
        echo "      Fixed: $(basename $BINARY)"
    fi
done

# Also fix libssl's reference to libcrypto
if [ -f "${FRAMEWORKS_DIR}/libssl.3.dylib" ]; then
    install_name_tool -change \
        /opt/homebrew/opt/openssl@3/lib/libcrypto.3.dylib \
        @loader_path/libcrypto.3.dylib \
        "${FRAMEWORKS_DIR}/libssl.3.dylib" 2>/dev/null || true
fi

# ── Step 3: Code sign ────────────────────────────────────────────────────
echo ""
echo "[3/${TOTAL_STEPS}] Code signing..."
if [ "$SKIP_SIGN" = "true" ]; then
    echo "      SKIPPED (SKIP_SIGN=true)"
else
    # Sign all frameworks and dylibs first
    find "${APP_PATH}" -type f \( -name "*.dylib" -o -name "*.so" -o -name "*.framework" \) \
        -exec codesign --force --sign "${SIGN_IDENTITY}" \
              --timestamp --options runtime \
              --entitlements "${ENTITLEMENTS}" {} \; 2>/dev/null || true

    # Sign mosquitto binaries inside Frameworks/
    for BIN in mosquitto mosquitto_passwd; do
        if [ -f "${FRAMEWORKS_DIR}/${BIN}" ]; then
            codesign --force --sign "${SIGN_IDENTITY}" \
                --timestamp --options runtime \
                --entitlements "${ENTITLEMENTS}" \
                "${FRAMEWORKS_DIR}/${BIN}"
        fi
    done

    # Sign the main app bundle
    codesign --force --deep --sign "${SIGN_IDENTITY}" \
        --timestamp --options runtime \
        --entitlements "${ENTITLEMENTS}" \
        "${APP_PATH}"

    echo "      Signed: ${APP_PATH}"
    codesign -vvv "${APP_PATH}" 2>&1 | tail -1
fi

# ── Step 4: Notarize ─────────────────────────────────────────────────────
echo ""
echo "[4/${TOTAL_STEPS}] Notarization..."
if [ "$SKIP_SIGN" = "true" ] || [ "$SKIP_NOTARIZE" = "true" ]; then
    echo "      SKIPPED"
else
    ZIP_PATH="${LOCAL_BUILD_DIR}/${APP_NAME}-notarize.zip"
    ditto -c -k --keepParent "${APP_PATH}" "${ZIP_PATH}"

    echo "      Submitting to Apple..."
    xcrun notarytool submit "${ZIP_PATH}" \
        --keychain-profile "${NOTARIZE_PROFILE}" \
        --wait

    echo "      Stapling ticket..."
    xcrun stapler staple "${APP_PATH}"
    echo "      Notarization complete"

    rm -f "${ZIP_PATH}"
fi

# ── Step 5: Create DMG ───────────────────────────────────────────────────
echo ""
echo "[5/${TOTAL_STEPS}] Creating DMG..."
if [ "$SKIP_DMG" = "true" ]; then
    echo "      SKIPPED"
else
    DMG_NAME="${APP_NAME} ${APP_VERSION} ${ARCH}.dmg"
    DMG_PATH="${DMG_DIR}/${DMG_NAME}"

    # Remove old DMG if exists
    rm -f "${DMG_PATH}"

    # Create temporary DMG directory
    DMG_STAGE="${LOCAL_BUILD_DIR}/dmg_stage"
    rm -rf "${DMG_STAGE}"
    mkdir -p "${DMG_STAGE}"

    # Copy app
    ditto "${APP_PATH}" "${DMG_STAGE}/${APP_NAME} ${APP_VERSION}.app"

    # Add symlink to Applications
    ln -s /Applications "${DMG_STAGE}/Applications"

    # Create DMG
    hdiutil create -volname "${APP_NAME} ${APP_VERSION}" \
        -srcfolder "${DMG_STAGE}" \
        -ov -format UDZO \
        "${DMG_PATH}"

    echo "      DMG: ${DMG_PATH}"

    rm -rf "${DMG_STAGE}"
fi

# ── Done ─────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "BUILD COMPLETE: ${APP_NAME} ${APP_VERSION} ${ARCH}"
echo "  App:  ${APP_PATH}"
[ "$SKIP_DMG" != "true" ] && echo "  DMG:  ${DMG_DIR}/${APP_NAME} ${APP_VERSION} ${ARCH}.dmg"
echo "=========================================="
