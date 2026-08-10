#!/usr/bin/env python3
"""
github_sync.py — Push a local file to bondtk/bondtk.github.io via GitHub API.

Usage:
    python3 github_sync.py <relative-path-in-repo>

Example:
    python3 github_sync.py index.html
    python3 github_sync.py css/style.css
"""

import sys
import os
import base64
import json
import time
import ssl
import urllib.request
import urllib.error

# macOS system Python often lacks root certs; use unverified context for this local push script
_SSL_CTX = ssl._create_unverified_context()

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO         = "bondtk/bondtk.github.io"
BRANCH       = "main"
LOCAL_ROOT   = os.path.dirname(os.path.abspath(__file__))
API_BASE     = "https://api.github.com"
# ──────────────────────────────────────────────────────────────────────────────

if not GITHUB_TOKEN:
    print("Error: set the GITHUB_TOKEN environment variable before running this script.")
    sys.exit(1)


def gh_request(method, path, body=None, retries=3):
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"token {GITHUB_TOKEN}")
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"GitHub API error {e.code}: {err_body}")
            sys.exit(1)
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"retrying in {wait}s... ", end="", flush=True)
                time.sleep(wait)
            else:
                print(f"failed after {retries} attempts: {e}")
                sys.exit(1)


def push_file(repo_path):
    """Read a local file and push it to GitHub, creating or updating as needed."""
    local_path = os.path.join(LOCAL_ROOT, repo_path)

    if not os.path.exists(local_path):
        print(f"Error: file not found: {local_path}")
        sys.exit(1)

    with open(local_path, "rb") as f:
        content_bytes = f.read()
    content_b64 = base64.b64encode(content_bytes).decode()

    # Get current SHA (required for updates; None if file doesn't exist yet)
    sha = None
    try:
        existing = gh_request("GET", f"/repos/{REPO}/contents/{repo_path}?ref={BRANCH}")
        sha = existing.get("sha")
    except SystemExit:
        pass  # File doesn't exist yet — that's fine, we'll create it

    payload = {
        "message": f"Update {repo_path}",
        "content": content_b64,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha

    result = gh_request("PUT", f"/repos/{REPO}/contents/{repo_path}", payload)
    commit_sha = result.get("commit", {}).get("sha", "")[:7]
    action = "Updated" if sha else "Created"
    print(f"{action} {repo_path} — commit {commit_sha}")


def push_all():
    """Push every tracked file in the repo (html, css, js, images)."""
    extensions = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".txt"}
    skip = {"github_sync.py"}

    pushed = 0
    for dirpath, dirnames, filenames in os.walk(LOCAL_ROOT):
        # Skip hidden dirs
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fname in filenames:
            if fname in skip or fname.startswith("."):
                continue
            _, ext = os.path.splitext(fname)
            if ext.lower() not in extensions:
                continue
            full = os.path.join(dirpath, fname)
            repo_path = os.path.relpath(full, LOCAL_ROOT).replace("\\", "/")
            print(f"Pushing {repo_path}...", end=" ", flush=True)
            push_file(repo_path)
            pushed += 1
            time.sleep(0.5)  # be polite to the API

    print(f"\nDone — {pushed} file(s) pushed to {REPO}.")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No argument → push everything
        push_all()
    elif len(sys.argv) == 2:
        push_file(sys.argv[1])
    else:
        print("Usage: python3 github_sync.py [<file>]")
        sys.exit(1)
