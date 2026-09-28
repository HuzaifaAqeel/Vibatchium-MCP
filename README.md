# Vibatchium-MCP

**Stealth browser automation for agents**: N parallel headless Chrome
sessions exposed as **MCP tools**, plus an encrypted **credential vault**
with TOTP — so an agent can stay logged in and act unattended, with no
human in front of the box.

```
 agent ──MCP stdio──▶ vibatchium-mcp ──┬──▶ session 1 ──▶ headless Chrome ──▶ site A (logged in)
                                       ├──▶ session 2 ──▶ headless Chrome ──▶ site B
                                       └──▶ vault ──▶ encrypted creds + TOTP codes
```

## MCP tools

| Tool | What it does |
|---|---|
| `session_open` / `session_list` / `session_close` | manage N parallel browser sessions |
| `navigate` | go to a URL, return title + text |
| `snapshot` | current page text snapshot |
| `click` / `type_text` | interact (typed secrets are redacted from output) |
| `extract` | pull named fields from page text |
| `screenshot` | capture PNG of the current page |
| `vault_store` / `vault_get` / `vault_list` | encrypted credential storage |
| `vault_totp` | current RFC 6238 code for a stored TOTP secret |

## Quickstart

```bash
pip install -r requirements.txt

# Demo mode: scripted backend, no browser needed — full tool surface works
python -m vibatchium_mcp.cli explore https://example.com --demo
python -m vibatchium_mcp.cli screenshot https://example.com shot.png --demo

# Credential vault (key via VIBATCHIUM_VAULT_KEY env var)
python -m vibatchium_mcp.cli vault-store mysite --username agent1 --demo
python -m vibatchium_mcp.cli vault-totp mysite --demo

# MCP server over stdio (point your agent at it)
python -m vibatchium_mcp.cli mcp --demo

# Real stealth browsing (headless Chromium)
pip install -r requirements-full.txt
python -m playwright install chromium
python -m vibatchium_mcp.cli explore https://example.com
```

Register with any MCP client (Claude Code, Cursor, etc.):

```json
{
  "mcpServers": {
    "vibatchium-mcp": {
      "command": "python",
      "args": ["-m", "vibatchium_mcp.cli", "mcp"],
      "cwd": "/path/to/vibatchium-mcp"
    }
  }
}
```

## Design notes

- **Stealth defaults** — real backend launches Chromium with
  anti-automation flags (`disable-blink-features=AutomationControlled`,
  realistic UA + viewport) and one persistent context per session, so
  logins and cookies survive across tool calls.
- **Vault security** — Fernet (XSalsa20-Poly1305-class AEAD) encryption
  when `cryptography` is installed; the key comes only from
  `VIBATCHIUM_VAULT_KEY`. Passwords are never echoed by the CLI and typed
  secrets are redacted from tool output. TOTP is pure-stdlib RFC 6238.
- **Graceful degradation** — Playwright is lazy-imported. Without it the
  demo backend serves the identical tool surface with scripted pages, so
  agent prompts and integrations are testable offline.

## Env vars

`VIBATCHIUM_VAULT_KEY` (required for real use), `VIBATCHIUM_VAULT_PATH`,
`VIBATCHIUM_DATA_DIR`, `VIBATCHIUM_DEMO=1` (force demo backend).

## Tests

```bash
python -m pytest tests/ -v   # offline: demo backend + vault + RFC 6238 vector
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
