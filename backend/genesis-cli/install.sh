#!/bin/sh
# Genesis CLI installer — Linux and macOS.
# Usage: sh install.sh [SERVER_URL]   (default http://127.0.0.1:8000)
set -e
SERVER="${1:-http://127.0.0.1:8000}"
DEST="${HOME}/.genesis"
command -v python3 >/dev/null || { echo "python3 is required (https://www.python.org/downloads/)"; exit 1; }
mkdir -p "$DEST"
echo "downloading genesis cli from ${SERVER} ..."
python3 -c "import urllib.request; urllib.request.urlretrieve('${SERVER}/api/download/cli', '${DEST}/cli.zip')"
python3 -c "import zipfile; zipfile.ZipFile('${DEST}/cli.zip').extractall('${DEST}')"
chmod +x "${DEST}/genesis"
ln -sf "${DEST}/genesis" /usr/local/bin/genesis 2>/dev/null || true
echo "installed to ${DEST}/genesis"
echo "try:  GENESIS_URL=${SERVER} genesis status"
echo "build:  GENESIS_URL=${SERVER} genesis new \"Build me a website for my clothing business\""
