#!/usr/bin/env python3
"""fetch.py - pull one or all agent-gates into .gates/<name>/ (stdlib only).

Usage:
  python fetch.py --list
  python fetch.py loop-gate
  python fetch.py --all [--dir PATH] [--ref main]

Set GITHUB_TOKEN to raise the API rate limit. No git needed.
"""
import argparse
import json
import os
import sys
import urllib.request

OWNER = "chenhz01"
GATES = ["loop-gate",
    "permission-gate",
    "context-gate",
    "instruction-gate",
    "output-gate",
    "memory-expiry-gate",
    "drift-gate",
    "price-gate",
    "complexity-ceiling",
    "deadcode-gate",
    "docrot-gate",
    "leak-gate",
    "backup-gate",
    "trail-gate"]
API = "https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"
RAW = "https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"


def _get(url, raw=False):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "agent-gates-fetch")
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if raw else json.loads(data.decode("utf-8"))


def fetch(repo, dest, ref="main"):
    tree = _get(API.format(owner=OWNER, repo=repo, ref=ref))
    blobs = [e for e in tree.get("tree", []) if e.get("type") == "blob"]
    if not blobs:
        raise SystemExit("no files found for " + repo)
    out = os.path.join(dest, repo)
    for e in blobs:
        path = e["path"]
        target = os.path.join(out, *path.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(_get(RAW.format(owner=OWNER, repo=repo, ref=ref, path=path), raw=True))
    return out, len(blobs)


def main():
    ap = argparse.ArgumentParser(prog="fetch.py", description="Fetch agent-gates (stdlib only).")
    ap.add_argument("names", nargs="*", help="gate repo name(s), e.g. loop-gate")
    ap.add_argument("--all", action="store_true", help="fetch every gate")
    ap.add_argument("--list", action="store_true", help="list gate names and exit")
    ap.add_argument("--dir", default=".gates")
    ap.add_argument("--ref", default="main")
    a = ap.parse_args()

    if a.list:
        for n in GATES:
            print(n)
        return 0

    names = GATES if a.all else a.names
    if not names:
        ap.error("give at least one gate name, --all, or --list")
    bad = [n for n in names if n not in GATES]
    if bad:
        ap.error("unknown gate(s): %s" % ", ".join(bad))

    os.makedirs(a.dir, exist_ok=True)
    for n in names:
        out, count = fetch(n, a.dir, a.ref)
        print("%-22s %3d files -> %s" % (n, count, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
