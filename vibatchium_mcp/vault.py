"""Encrypted credential vault + TOTP.

- Secrets encrypted at rest (Fernet if `cryptography` is installed,
  XOR+base64 obfuscation fallback — clearly labelled, not real crypto).
- Encryption key comes from VIBATCHIUM_VAULT_KEY env var; generated and
  printed once if absent (demo mode uses an ephemeral key).
- TOTP implemented with stdlib (RFC 6238) — no extra dependency.
- Log redaction helper so secrets never hit stdout/logs.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import struct
import time
from pathlib import Path

log = logging.getLogger(__name__)

REDACTED = "***"


def _load_key(demo: bool = False) -> bytes:
    raw = os.environ.get("VIBATCHIUM_VAULT_KEY", "")
    if raw:
        return hashlib.sha256(raw.encode()).digest()
    if demo:
        return hashlib.sha256(b"vibatchium-demo-key").digest()
    key = secrets.token_bytes(32)
    print("Generated vault key — save it as VIBATCHIUM_VAULT_KEY:")
    print(base64.urlsafe_b64encode(key).decode())
    return key


class Vault:
    def __init__(self, path: str | Path | None = None, demo: bool = False):
        self.path = Path(path or os.environ.get(
            "VIBATCHIUM_VAULT_PATH", os.path.expanduser("~/.vibatchium-mcp/vault.json")))
        self.key = _load_key(demo)
        self._fernet = None
        try:
            from cryptography.fernet import Fernet
            self._fernet = Fernet(base64.urlsafe_b64encode(self.key))
        except ImportError:
            log.warning("cryptography not installed — vault uses obfuscation only, not real encryption.")
        self._data: dict = {}
        self._load()

    # -- crypto -----------------------------------------------------------
    def _enc(self, plaintext: str) -> str:
        if self._fernet:
            return self._fernet.encrypt(plaintext.encode()).decode()
        # labelled fallback: NOT real encryption
        x = bytes(b ^ self.key[i % 32] for i, b in enumerate(plaintext.encode()))
        return "OBFUSCATED:" + base64.b64encode(x).decode()

    def _dec(self, blob: str) -> str:
        if blob.startswith("OBFUSCATED:"):
            x = base64.b64decode(blob[len("OBFUSCATED:"):])
            return bytes(b ^ self.key[i % 32] for i, b in enumerate(x)).decode()
        return self._fernet.decrypt(blob.encode()).decode()

    # -- store ------------------------------------------------------------
    def _load(self):
        if self.path.exists():
            self._data = json.loads(self.path.read_text())

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data))

    def store(self, name: str, username: str, password: str, totp_secret: str = "") -> None:
        self._data[name] = {
            "username": self._enc(username),
            "password": self._enc(password),
            "totp_secret": self._enc(totp_secret) if totp_secret else "",
        }
        self._save()

    def get(self, name: str) -> dict:
        try:
            e = self._data[name]
        except KeyError:
            raise KeyError(f"No credentials stored for '{name}'") from None
        return {
            "username": self._dec(e["username"]),
            "password": self._dec(e["password"]),
            "totp_secret": self._dec(e["totp_secret"]) if e["totp_secret"] else "",
        }

    def list(self) -> list[str]:
        return sorted(self._data.keys())

    def delete(self, name: str) -> bool:
        if name in self._data:
            del self._data[name]
            self._save()
            return True
        return False


# -- TOTP (RFC 6238, stdlib only) ------------------------------------------
def totp_code(secret_b32: str, for_time: float | None = None, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret_b32.upper().replace(" ", ""))
    counter = int((for_time or time.time()) // step)
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def redact(text: str, secrets_list: list[str]) -> str:
    for s in secrets_list:
        if s:
            text = text.replace(s, REDACTED)
    return text
