"""Smoke tests — demo backend + vault, no browser, no network."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vibatchium_mcp import server as tools
from vibatchium_mcp.vault import totp_code, redact


def test_totp_rfc6238_vector():
    # RFC 6238 test vector: secret "12345678901234567890", T=59 -> 287082
    secret_b32 = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp_code(secret_b32, for_time=59, digits=8) == "94287082"
    assert len(totp_code(secret_b32)) == 6


def test_vault_roundtrip_and_redaction():
    with tempfile.TemporaryDirectory() as d:
        tools.configure(demo=True, vault_path=str(Path(d) / "vault.json"))
        tools.vault_store("mysite", "agent1", "s3cr3t-pw", "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ")
        assert tools.vault_list() == ["mysite"]
        creds = tools.vault_get("mysite")
        assert creds["username"] == "agent1" and creds["password"] == "s3cr3t-pw"
        assert len(creds["totp_now"]) == 6
        # vault file must not contain the plaintext password
        raw = (Path(d) / "vault.json").read_text()
        assert "s3cr3t-pw" not in raw
        assert redact("login with s3cr3t-pw now", ["s3cr3t-pw"]) == "login with *** now"
        assert tools.vault().delete("mysite") is True
        assert tools.vault_list() == []


def test_browser_tool_flow_demo():
    tools.configure(demo=True)
    s = tools.session_open()
    assert s["backend"] == "demo"
    sid = s["session_id"]

    page = tools.navigate(sid, "https://example.com")
    assert page["title"] == "Example Domain"
    assert "illustrative examples" in page["text"]

    snap = tools.snapshot(sid)
    assert snap["url"] == "https://example.com"

    ext = tools.extract(sid, "examples")
    assert "examples" in ext

    assert "clicked" in tools.click(sid, "#login")["result"]
    typed = tools.type_text(sid, "#pw", "hunter2")
    assert "hunter2" not in typed["result"]  # secret redacted

    shot = tools.screenshot(sid, "/tmp/vb_demo_test.png")
    assert Path(shot["path"]).exists()

    sessions = tools.session_list()
    assert any(x["id"] == sid for x in sessions)
    tools.session_close(sid)
    assert all(x["id"] != sid for x in tools.session_list())


def test_tool_registry_complete():
    expected = {"session_open", "session_list", "session_close", "navigate",
                "snapshot", "click", "type_text", "extract", "screenshot",
                "vault_store", "vault_get", "vault_list", "vault_totp"}
    assert expected <= set(tools.TOOLS)
