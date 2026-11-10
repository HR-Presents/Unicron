#!/usr/bin/env python3
"""Read-only installation preflight. Does not initialize the API or modify databases."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CHECKS = []

def check(name, ok, detail, required=True):
    CHECKS.append({"check": name, "status": "PASS" if ok else ("FAIL" if required else "WARN"), "detail": detail})

def version(command):
    if not shutil.which(command):
        return None
    try:
        result = subprocess.run([command, "--version"], capture_output=True, text=True, timeout=5, check=False)
        return (result.stdout or result.stderr).strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None

def probe(url, token=""):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=4) as response:
        return json.load(response)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Probe running API and model (no inference)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()
    check("Platform", sys.platform.startswith("linux"), "Linux/WSL2 is the supported full-workflow platform", False)
    check("Python", sys.version_info[:2] == (3, 12), f"Detected {sys.version.split()[0]}; documented version is 3.12")
    check("Virtual environment", (ROOT / ".venv/bin/python").is_file(), "Expected .venv/bin/python")
    node = version("node")
    try:
        major, minor = [int(x) for x in node.lstrip("v").split(".")[:2]] if node else (0, 0)
    except ValueError:
        major, minor = 0, 0
    check("Node.js", (major, minor) >= (22, 12), f"Detected {node or 'not installed'}; requires 22.12+")
    check("npm", bool(version("npm")), "npm executable available" if version("npm") else "npm not found")
    check("Frontend install", (ROOT / "frontend/node_modules/.bin/vite").exists(), "Vite executable in frontend/node_modules")
    for module, package in [("fastapi", "fastapi"), ("uvicorn", "uvicorn"), ("pydantic", "pydantic"), ("multipart", "python-multipart"), ("pypdf", "pypdf")]:
        try:
            found = importlib.metadata.version(package)
            check("Python dependency: " + package, True, found)
        except importlib.metadata.PackageNotFoundError:
            check("Python dependency: " + package, False, "Install backend/requirements.txt into .venv")
    db = Path(os.getenv("CIVITAS_DB_PATH", str(ROOT / "backend/data/civitas.sqlite3"))).expanduser()
    check("Workspace database", db.is_file(), "Existing SQLite workspace detected" if db.is_file() else "Database absent; first API startup will create it", False)
    archive = Path(os.getenv("CIVITAS_EVIDENCE_ARCHIVE_PATH", str(db.with_name("civitas.sqlite3")))).expanduser()
    if archive.is_file():
        try:
            connection = sqlite3.connect("file:" + archive.resolve().as_posix() + "?mode=ro", uri=True)
            try:
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                check("Evidence archive", "evidence_passages" in tables, "Read-only SQLite archive found; evidence_passages table " + ("present" if "evidence_passages" in tables else "missing"), False)
            finally:
                connection.close()
        except sqlite3.Error:
            check("Evidence archive", False, "Archive cannot be opened read-only", False)
    else:
        check("Evidence archive", False, "No archive at configured path; evidence must be imported separately", False)
    model_id = os.getenv("CIVITAS_LLM_MODEL", "")
    check("Model configuration", bool(model_id), "CIVITAS_LLM_MODEL set" if model_id else "Set CIVITAS_LLM_MODEL to the served model ID", False)
    check("API authentication", bool(os.getenv("CIVITAS_API_KEY")), "API key configured" if os.getenv("CIVITAS_API_KEY") else "Set CIVITAS_API_KEY before exposing API beyond localhost", False)
    if args.live:
        api = os.getenv("UNICRON_API_URL", "http://127.0.0.1:42515").rstrip("/")
        model = os.getenv("CIVITAS_LLM_BASE_URL", "http://127.0.0.1:42516/v1").rstrip("/")
        for name, url, token in [
            ("API health", api + "/api/health", ""),
            ("Authenticated API", api + "/api/cases", os.getenv("UNICRON_API_TOKEN") or os.getenv("CIVITAS_API_KEY", "")),
            ("Model server", model + "/models", os.getenv("CIVITAS_LLM_API_KEY", "")),
        ]:
            try:
                payload = probe(url, token)
                if name == "Model server":
                    ids = [x.get("id") for x in payload.get("data", []) if isinstance(x, dict)]
                    check(name, bool(ids) and (not model_id or model_id in ids), "Model endpoint reachable; " + ("configured ID advertised" if model_id in ids else "check CIVITAS_LLM_MODEL"))
                else:
                    check(name, True, "HTTP JSON response received")
            except (OSError, ValueError, TypeError, urllib.error.HTTPError) as exc:
                check(name, False, "Connection or JSON validation failed (" + type(exc).__name__ + ")")
    if args.json:
        print(json.dumps({"checks": CHECKS, "summary": {status: sum(x["status"] == status for x in CHECKS) for status in ("PASS", "WARN", "FAIL")}}, indent=2))
    else:
        for item in CHECKS:
            print(f"[{item['status']}] {item['check']}: {item['detail']}")
        print("Read-only preflight. For actual six-agent inference use scripts/verify-live.py.")
    return int(any(x["status"] == "FAIL" for x in CHECKS))

if __name__ == "__main__":
    sys.exit(main())
