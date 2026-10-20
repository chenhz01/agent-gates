#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 chenhz01 — see LICENSE, LICENSE-SPEC and NOTICE
"""fetch.py - pull one or all agent-gates into .gates/<name>/ (stdlib only).

Usage:
  python fetch.py --list
  python fetch.py loop-gate
  python fetch.py --all [--dir PATH] [--ref main]

Set GITHUB_TOKEN to raise the API rate limit. No git needed.
"""
import argparse
import io
import json
import os
import sys
import tarfile
import time
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
TARBALL = "https://codeload.github.com/{owner}/{repo}/tar.gz/refs/heads/{ref}"


def _get(url, raw=False, tries=4):
    """一个 URL 重试 tries 次（连接被重置在这个网络上很常见）。"""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "agent-gates-fetch")
            tok = os.environ.get("GITHUB_TOKEN")
            if tok:
                req.add_header("Authorization", "Bearer " + tok)
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            return data if raw else json.loads(data.decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - 网络层什么都可能抛
            last = e
            if i < tries - 1:
                time.sleep(1.5 * (i + 1))
    raise SystemExit("GET failed after %d tries: %s -> %s" % (tries, url, last))


def fetch(repo, dest, ref="main"):
    """整仓一次拿到：优先 codeload tarball（1 请求、原子），失败再退回逐文件。"""
    out = os.path.join(dest, repo)
    try:
        blob = _get(TARBALL.format(owner=OWNER, repo=repo, ref=ref), raw=True)
    except SystemExit:
        return _fetch_by_file(repo, out, ref)
    n = 0
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            parts = m.name.split("/", 1)     # 去掉 tarball 顶层 <repo>-<tag>/ 前缀
            if len(parts) < 2 or not parts[1]:
                continue
            target = os.path.join(out, *parts[1].split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            src = tf.extractfile(m)
            if src is None:
                continue
            with open(target, "wb") as f:
                f.write(src.read())
            n += 1
    if not n:
        raise SystemExit("no files found for " + repo)
    return out, n


def _fetch_by_file(repo, out, ref):
    """兜底路径：tree API 列文件 + 逐文件 raw（慢，但单点失败不影响整仓）。"""
    tree = _get(API.format(owner=OWNER, repo=repo, ref=ref))
    blobs = [e for e in tree.get("tree", []) if e.get("type") == "blob"]
    if not blobs:
        raise SystemExit("no files found for " + repo)
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
    failed = []
    for n in names:
        try:
            out, count = fetch(n, a.dir, a.ref)
        except (SystemExit, Exception) as e:  # noqa: BLE001 - 一仓失败不能拖垮整批
            failed.append(n)
            print("%-22s FAILED -> %s" % (n, e), file=sys.stderr)
            continue
        print("%-22s %3d files -> %s" % (n, count, out))
    if failed:
        print("failed: %s" % ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
