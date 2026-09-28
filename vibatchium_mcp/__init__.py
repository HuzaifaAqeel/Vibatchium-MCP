"""Vibatchium-MCP — stealth browser automation for agents.

N parallel headless Chrome sessions exposed as MCP tools, plus an
encrypted credential vault with TOTP. Playwright is lazy-loaded;
without it (or with --demo) a scripted demo backend runs the same
tool surface so the whole flow is testable offline.
"""

__version__ = "1.0.0"
