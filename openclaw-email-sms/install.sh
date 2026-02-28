#!/usr/bin/env bash
# install.sh — Install Commune email & SMS skills for OpenClaw
# Usage: bash install.sh
set -euo pipefail

SKILLS_DIR="${HOME}/.openclaw/workspace/skills"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Colours ────────────────────────────────────────────────────────────────────
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

info()  { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
error() { echo -e "${RED}✗${NC} $*" >&2; }

# ── Preflight checks ──────────────────────────────────────────────────────────
echo ""
echo "Installing Commune skills for OpenClaw..."
echo ""

# Check OpenClaw is installed
if ! command -v openclaw &>/dev/null && [ ! -d "${HOME}/.openclaw" ]; then
  error "OpenClaw not found. Install it first: https://github.com/openclaw/openclaw"
  exit 1
fi

# Check Node.js is available (needed by commune.js CLI helpers)
if ! command -v node &>/dev/null; then
  error "Node.js is required (https://nodejs.org). Install Node 18+ and re-run."
  exit 1
fi

# ── Create skills directory ───────────────────────────────────────────────────
mkdir -p "${SKILLS_DIR}"

# ── Install commune-email skill ───────────────────────────────────────────────
COMMUNE_EMAIL_DEST="${SKILLS_DIR}/commune-email"

if [ -d "${COMMUNE_EMAIL_DEST}" ]; then
  warn "commune-email skill already installed — updating..."
  rm -rf "${COMMUNE_EMAIL_DEST}"
fi

cp -r "${SCRIPT_DIR}/skills/commune-email" "${COMMUNE_EMAIL_DEST}"

# Install npm dependencies for the CLI helper
if [ -f "${COMMUNE_EMAIL_DEST}/package.json" ]; then
  (cd "${COMMUNE_EMAIL_DEST}" && npm install --silent)
fi

chmod +x "${COMMUNE_EMAIL_DEST}/commune.js"
info "commune-email skill installed"

# ── Install commune-sms skill ─────────────────────────────────────────────────
COMMUNE_SMS_DEST="${SKILLS_DIR}/commune-sms"

if [ -d "${COMMUNE_SMS_DEST}" ]; then
  warn "commune-sms skill already installed — updating..."
  rm -rf "${COMMUNE_SMS_DEST}"
fi

cp -r "${SCRIPT_DIR}/skills/commune-sms" "${COMMUNE_SMS_DEST}"

if [ -f "${COMMUNE_SMS_DEST}/package.json" ]; then
  (cd "${COMMUNE_SMS_DEST}" && npm install --silent)
fi

chmod +x "${COMMUNE_SMS_DEST}/commune-sms.js"
info "commune-sms skill installed"

# ── Environment variable check ────────────────────────────────────────────────
echo ""
echo "Checking environment variables..."

OPENCLAW_CONFIG="${HOME}/.openclaw/openclaw.json"
ENV_FILE="${HOME}/.openclaw/.env"

missing_vars=()

if [ ! -f "${ENV_FILE}" ]; then
  warn "No .env found at ${ENV_FILE}"
  missing_vars+=("COMMUNE_API_KEY" "COMMUNE_PHONE_NUMBER_ID")
else
  # Source the .env and check for required vars
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}" 2>/dev/null || true
  set +a

  if [ -z "${COMMUNE_API_KEY:-}" ]; then
    missing_vars+=("COMMUNE_API_KEY")
  fi
fi

if [ ${#missing_vars[@]} -gt 0 ]; then
  echo ""
  warn "Missing environment variables. Add these to ${ENV_FILE}:"
  echo ""
  for var in "${missing_vars[@]}"; do
    echo "  export ${var}=your_value_here"
  done
  echo ""
  echo "  Get your API key at: https://commune.email/dashboard"
  echo ""
else
  info "Environment variables look good"
fi

# ── Verify installation ───────────────────────────────────────────────────────
echo ""
echo "Verifying installation..."

if [ -f "${COMMUNE_EMAIL_DEST}/SKILL.md" ]; then
  info "commune-email SKILL.md present"
else
  error "commune-email SKILL.md missing — installation may have failed"
  exit 1
fi

if [ -f "${COMMUNE_SMS_DEST}/SKILL.md" ]; then
  info "commune-sms SKILL.md present"
else
  error "commune-sms SKILL.md missing — installation may have failed"
  exit 1
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Add COMMUNE_API_KEY to ${ENV_FILE}"
echo "  2. Restart OpenClaw: openclaw restart (or close and reopen)"
echo "  3. Try: 'Check my emails' or 'Send a text to +1 555 000 1234'"
echo ""
echo "Docs: https://github.com/shanjairaj7/email-for-agents/tree/main/openclaw-email-sms"
