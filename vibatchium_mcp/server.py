"""MCP server exposing the browser fleet + vault as agent tools.

Tools are plain functions in TOOLS (testable without the `mcp` package);
create_server() wraps them in a FastMCP stdio server when available.
"""
import json
import logging
import os
from pathlib import Path

from .browser import SessionPool
from .vault import Vault, totp_code, redact

log = logging.getLogger(__name__)

_pool: SessionPool | None = None
_vault: Vault | None = None
_demo = False


def configure(demo: bool = False, max_sessions: int = 4, vault_path=None):
    global _pool, _vault, _demo
    _demo = demo
    _pool = SessionPool(max_sessions=max_sessions, demo=demo)
    _vault = Vault(vault_path, demo=demo)


def pool() -> SessionPool:
    if _pool is None:
        configure(demo=os.environ.get("VIBATCHIUM_DEMO", "").lower() in ("1", "true"))
    return _pool


def vault() -> Vault:
    if _vault is None:
        configure(demo=os.environ.get("VIBATCHIUM_DEMO", "").lower() in ("1", "true"))
    return _vault


# -- browser tools ----------------------------------------------------------
def session_open() -> dict:
    s = pool().open()
    return {"session_id": s.id, "backend": s.backend.name}


def session_list() -> list[dict]:
    return pool().list()


def session_close(session_id: str) -> dict:
    pool().close(session_id)
    return {"closed": session_id}


def navigate(session_id: str, url: str) -> dict:
    s = pool().get(session_id)
    p = s.backend.navigate(s, url)
    return {"url": p.url, "title": p.title, "text": p.text[:4000]}


def snapshot(session_id: str) -> dict:
    s = pool().get(session_id)
    if not s.current:
        return {"url": None, "text": ""}
    return {"url": s.current.url, "title": s.current.title, "text": s.current.text[:4000]}


def click(session_id: str, selector: str) -> dict:
    s = pool().get(session_id)
    return {"result": s.backend.click(s, selector)}


def type_text(session_id: str, selector: str, text: str) -> dict:
    s = pool().get(session_id)
    # never echo the typed secret back
    return {"result": redact(s.backend.type(s, selector, text), [text])}


def extract(session_id: str, fields: str = "") -> dict:
    """Extract structured fields (comma-separated) from current page text."""
    s = pool().get(session_id)
    text = s.current.text if s.current else ""
    out = {"url": s.current.url if s.current else None}
    for f in [x.strip() for x in fields.split(",") if x.strip()]:
        out[f] = next((ln for ln in text.splitlines() if f.lower() in ln.lower()), "")
    return out


def screenshot(session_id: str, path: str = "") -> dict:
    s = pool().get(session_id)
    path = path or str(Path(os.environ.get("VIBATCHIUM_DATA_DIR",
                                           "/tmp/vibatchium-mcp")) / f"{s.id}.png")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return {"path": s.backend.screenshot(s, path)}


# -- vault tools --------------------------------------------------------------
def vault_store(name: str, username: str, password: str, totp_secret: str = "") -> dict:
    vault().store(name, username, password, totp_secret)
    return {"stored": name}


def vault_get(name: str) -> dict:
    creds = vault().get(name)
    out = {"username": creds["username"], "password": creds["password"]}
    if creds["totp_secret"]:
        out["totp_now"] = totp_code(creds["totp_secret"])
    return out


def vault_list() -> list[str]:
    return vault().list()


def vault_totp(name: str) -> dict:
    secret = vault().get(name)["totp_secret"]
    if not secret:
        raise ValueError(f"No TOTP secret stored for '{name}'")
    return {"code": totp_code(secret)}


TOOLS = {
    "session_open": session_open,
    "session_list": session_list,
    "session_close": session_close,
    "navigate": navigate,
    "snapshot": snapshot,
    "click": click,
    "type_text": type_text,
    "extract": extract,
    "screenshot": screenshot,
    "vault_store": vault_store,
    "vault_get": vault_get,
    "vault_list": vault_list,
    "vault_totp": vault_totp,
}


def create_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        raise RuntimeError(
            "The 'mcp' package is not installed (pip install -r requirements.txt)."
        ) from e
    mcp = FastMCP("vibatchium-mcp")
    for name, fn in TOOLS.items():
        mcp.tool(name=name)(fn)
    return mcp


def main():
    import argparse
    p = argparse.ArgumentParser(description="vibatchium-mcp MCP server (stdio)")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--max-sessions", type=int, default=4)
    args = p.parse_args()
    configure(demo=args.demo, max_sessions=args.max_sessions)
    create_server().run()
