"""Resolve the shared evidence archive independently of the code checkout."""
import os
from pathlib import Path


def evidence_archive_path(workspace_db):
    configured = os.getenv('CIVITAS_EVIDENCE_ARCHIVE_PATH', '').strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if workspace_db:
        return Path(workspace_db).expanduser().resolve().parent / 'civitas.sqlite3'
    return Path(__file__).resolve().parents[1] / 'data' / 'civitas.sqlite3'
