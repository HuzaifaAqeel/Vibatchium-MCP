#!/usr/bin/env python3
"""vb — CLI for the stealth browser fleet.

    python -m vibatchium_mcp.cli explore https://example.com --demo
    python -m vibatchium_mcp.cli screenshot https://example.com out.png --demo
    python -m vibatchium_mcp.cli vault-store mysite --demo
    python -m vibatchium_mcp.cli mcp --demo        # run MCP server (stdio)
"""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vibatchium_mcp import server as tools


def cmd_explore(args):
    tools.configure(demo=args.demo)
    s = tools.session_open()
    print(f"session: {s['session_id']} (backend: {s['backend']})")
    page = tools.navigate(s["session_id"], args.url)
    print(f"title: {page['title']}\nurl:   {page['url']}\n")
    print(page["text"][:1500])
    tools.session_close(s["session_id"])


def cmd_screenshot(args):
    tools.configure(demo=args.demo)
    s = tools.session_open()
    tools.navigate(s["session_id"], args.url)
    out = tools.screenshot(s["session_id"], args.out)
    print(f"screenshot -> {out['path']}")
    tools.session_close(s["session_id"])


def cmd_sessions(args):
    tools.configure(demo=args.demo)
    for sess in tools.session_list():
        print(json.dumps(sess))


def cmd_vault_store(args):
    tools.configure(demo=args.demo, vault_path=args.vault)
    username = args.username or input("username: ")
    password = args.password or getpass.getpass("password: ")
    totp = args.totp or ""
    tools.vault_store(args.name, username, password, totp)
    print(f"stored credentials for '{args.name}' (password never echoed)")


def cmd_vault_list(args):
    tools.configure(demo=args.demo, vault_path=args.vault)
    for name in tools.vault_list():
        print(name)


def cmd_vault_totp(args):
    tools.configure(demo=args.demo, vault_path=args.vault)
    print(tools.vault_totp(args.name)["code"])


def cmd_mcp(args):
    tools.configure(demo=args.demo)
    tools.create_server().run()


def build_parser():
    p = argparse.ArgumentParser(prog="vb", description="Stealth browser fleet for agents")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--demo", action="store_true", help="scripted backend, no browser needed")
    common.add_argument("--vault", default=None, help="vault file path")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("explore", help="one call: open session, navigate, print text", parents=[common])
    e.add_argument("url")
    e.set_defaults(fn=cmd_explore)

    s = sub.add_parser("screenshot", help="capture a page screenshot", parents=[common])
    s.add_argument("url")
    s.add_argument("out", nargs="?", default="")
    s.set_defaults(fn=cmd_screenshot)

    l = sub.add_parser("sessions", help="list open sessions", parents=[common])
    l.set_defaults(fn=cmd_sessions)

    vs = sub.add_parser("vault-store", help="store credentials in the encrypted vault", parents=[common])
    vs.add_argument("name")
    vs.add_argument("--username", default="")
    vs.add_argument("--password", default="")
    vs.add_argument("--totp", default="", help="base32 TOTP secret (optional)")
    vs.set_defaults(fn=cmd_vault_store)

    vl = sub.add_parser("vault-list", help="list vault entries (names only)", parents=[common])
    vl.set_defaults(fn=cmd_vault_list)

    vt = sub.add_parser("vault-totp", help="print current TOTP code for an entry", parents=[common])
    vt.add_argument("name")
    vt.set_defaults(fn=cmd_vault_totp)

    m = sub.add_parser("mcp", help="run the MCP server over stdio", parents=[common])
    m.set_defaults(fn=cmd_mcp)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
