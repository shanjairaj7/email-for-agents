# Changelog

All notable changes to this repository are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added
- Ongoing example additions and improvements

---

## [0.4.0] — 2025-02-28

### Added
- OpenClaw email skill — installable `commune-email` skill with companion CLI helpers and an automated install script.

### Changed
- Master README reorganized with three sections: Platforms, Use Cases, Capabilities
- All Python agent files now load `.env` automatically on startup
- All `requirements.txt` files now pin minimum versions for reproducible installs

---

## [0.3.0] — 2025-02-25

### Added
- `use-cases/` section — five use case categories with working examples:
  - `customer-support/` — email agent, omnichannel
  - `hiring-and-recruiting/` — candidate outreach, interview scheduler
  - `sales-and-marketing/` — cold email sequences, newsletter
  - `research/` — email research agent
  - `notifications-and-alerts/` — incident alerts
- `capabilities/` section — six capability deep-dives:
  - `quickstart/`, `email-threading/`, `extraction/`, `search/`, `webhooks/`

---

## [0.2.0] — 2025-02-22

### Added
- `typescript/` — Webhook handler and multi-agent coordination in TypeScript
- `mcp-server/` — MCP server with Claude Desktop + Cursor configuration

---

## [0.1.0] — 2025-02-20

### Added
- Initial release with examples for four platforms:
  - `langchain/` — customer support, lead outreach
  - `crewai/` — support crew, outreach crew
  - `openai-agents/` — support agent, multi-agent handoff
  - `claude/` — support agent, extraction agent
- Master `README.md` with 60-second quickstart
- `.gitignore` covering Python, Node, and editor files
