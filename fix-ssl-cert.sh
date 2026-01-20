#!/bin/bash
# Fix SSL certificate for Faster Whisper Server (Let's Encrypt Staging)
# This script adds the staging root certificate to the certifi bundle in the venv

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
STAGING_CERT="/usr/local/share/ca-certificates/letsencrypt-stg-root-x1.crt"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Fixing SSL certificate for Faster Whisper Server..."
echo

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}Error: Virtual environment not found at $VENV_DIR${NC}"
    echo "Please create the venv first by running: python3 -m venv venv"
    exit 1
fi

# Check if staging cert exists
if [ ! -f "$STAGING_CERT" ]; then
    echo -e "${RED}Error: Staging certificate not found at $STAGING_CERT${NC}"
    echo
    echo "Please install it first:"
    echo "  wget https://letsencrypt.org/certs/staging/letsencrypt-stg-root-x1.pem"
    echo "  sudo cp letsencrypt-stg-root-x1.pem /usr/local/share/ca-certificates/letsencrypt-stg-root-x1.crt"
    echo "  sudo update-ca-certificates"
    exit 1
fi

# Find certifi cacert.pem
CERTIFI_BUNDLE=$(find "$VENV_DIR" -path "*/certifi/cacert.pem" 2>/dev/null | head -1)

if [ -z "$CERTIFI_BUNDLE" ]; then
    echo -e "${RED}Error: certifi bundle not found in venv${NC}"
    echo "Please install certifi: source venv/bin/activate && pip install certifi"
    exit 1
fi

echo "Found certifi bundle: $CERTIFI_BUNDLE"

# Check if staging cert is already in bundle
if grep -q "ISRG Root X2" "$CERTIFI_BUNDLE" && grep -q "staging" "$CERTIFI_BUNDLE" 2>/dev/null; then
    echo -e "${GREEN}✓ Staging certificate already present in certifi bundle${NC}"
    exit 0
fi

# Add staging cert to bundle
echo "Adding staging certificate to certifi bundle..."
cat "$STAGING_CERT" >> "$CERTIFI_BUNDLE"

echo -e "${GREEN}✓ Successfully added staging certificate to certifi bundle${NC}"
echo
echo "You can now use voicesnip with Faster Whisper Server over HTTPS."
