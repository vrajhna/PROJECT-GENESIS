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
if command -v genesis >/dev/null 2>&1; then
  echo "genesis is already on your PATH."
else
  echo "linking genesis into /usr/local/bin (may ask for your password)..."
  if sudo ln -sf "${DEST}/genesis" /usr/local/bin/genesis 2>/dev/null; then
    echo "linked: genesis is now on your PATH."
  else
    echo "no sudo access — run this now (or add it to ~/.bashrc):"
    echo "  export PATH=\"\$HOME/.genesis:\$PATH\""
  fi
fi
echo "installed to ${DEST}/genesis"
"${DEST}/genesis" --help >/dev/null 2>&1 && echo "self-test: genesis runs OK" || echo "self-test: binary present at ${DEST}/genesis"
echo "try:  GENESIS_URL=${SERVER} genesis status"
echo "build:  GENESIS_URL=${SERVER} genesis new \"Build me a website for my clothing business\""
