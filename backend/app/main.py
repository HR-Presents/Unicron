"""CIVITAS local API. Case records are persisted; AI execution is not simulated."""
from __future__ import annotations

import os
import hmac
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get('CIVITAS_DB_PATH', str(ROOT / 'data' / 'civitas.sqlite3')))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

@contextmanager
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

with db() as con:
    con.execute('''CREATE TABLE IF NOT EXISTS cases (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL,
        domain TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS audit (
        id TEXT PRIMARY KEY, case_id TEXT, action TEXT NOT NULL,
        detail TEXT NOT NULL, created_at TEXT NOT NULL)''')

app = FastAPI(title='CIVITAS API', version='0.3.0')

@app.middleware('http')
async def optional_api_auth(request, call_next):
    """Opt-in deployment-wide API authentication; local development stays unchanged."""
    from fastapi.responses import JSONResponse
    if request.method == 'OPTIONS' or request.url.path == '/api/health' or not request.url.path.startswith('/api/'):
        return await call_next(request)
    expected = os.getenv('CIVITAS_API_KEY', '').strip()
    if not expected:
        return await call_next(request)
    provided = request.headers.get('authorization', '')
    prefix = 'Bearer '
    if not provided.startswith(prefix) or not hmac.compare_digest(provided[len(prefix):], expected):
        return JSONResponse(status_code=401, content={'detail': 'API authentication required'})
    return await call_next(request)

app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000', 'http://127.0.0.1:3000'], allow_credentials=False, allow_methods=['GET','POST','PATCH','DELETE'], allow_headers=['*'])

class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    summary: str = Field(min_length=3, max_length=8000)
    domain: str = Field(default='Citizen services', max_length=100)
    priority: str = Field(default='Medium', pattern='^(Low|Medium|High)$')

class CaseUpdate(BaseModel):
    status: str = Field(pattern='^(New|Investigating|Review|Resolved)$')

def now():
    return datetime.now(timezone.utc).isoformat()

def record(con, case_id, action, detail):
    con.execute('INSERT INTO audit VALUES (?,?,?,?,?)', (str(uuid4()), case_id, action, detail, now()))

@app.get('/api/health')
def health():
    return {'status': 'ok', 'service': 'civitas-api', 'version': '0.3.0', 'llm': 'configured-endpoint-not-probed'}

@app.get('/api/cases')
def list_cases():
    with db() as con:
        return [dict(row) for row in con.execute('SELECT * FROM cases ORDER BY updated_at DESC')]

@app.post('/api/cases', status_code=201)
def create_case(case: CaseCreate):
    case_id = 'CIV-' + datetime.now(timezone.utc).strftime('%Y%m%d') + '-' + uuid4().hex[:6].upper()
    stamp = now()
    with db() as con:
        con.execute('INSERT INTO cases VALUES (?,?,?,?,?,?,?,?)', (case_id, case.title, case.summary, case.domain, case.priority, 'New', stamp, stamp))
        record(con, case_id, 'case.created', 'Case created by API user')
        return dict(con.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone())


@app.delete('/api/cases/{case_id}')
def delete_case(case_id: str):
    """Permanently delete a case and its case-owned investigation data."""
    with db() as con:
        existing = con.execute(
            'SELECT id FROM cases WHERE id=?',
            (case_id,)
        ).fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail='Case not found')

        active = con.execute("""
            SELECT id, status
            FROM investigation_jobs
            WHERE case_id=? AND status IN ('queued', 'running')
        """, (case_id,)).fetchall()

        if active:
            raise HTTPException(
                status_code=409,
                detail='Cannot delete a case while an investigation is queued or running.'
            )

        # Resolve dependent record IDs before deleting parent records.
        executions = [
            row[0] for row in con.execute(
                'SELECT id FROM investigation_execution WHERE case_id=?',
                (case_id,)
            )
        ]

        sessions = [
            row[0] for row in con.execute(
                'SELECT id FROM scenario_sessions WHERE case_id=?',
                (case_id,)
            )
        ]

        documents = [
            row[0] for row in con.execute(
                'SELECT id FROM evidence_documents WHERE case_id=?',
                (case_id,)
            )
        ]

        # Investigation event records belong to execution records.
        for execution_id in executions:
            con.execute(
                'DELETE FROM investigation_events WHERE run_id=?',
                (execution_id,)
            )

        # Scenario records.
        for session_id in sessions:
            con.execute(
                'DELETE FROM scenario_assessments WHERE session_id=?',
                (session_id,)
            )
            con.execute(
                'DELETE FROM scenario_stimuli WHERE session_id=?',
                (session_id,)
            )

        # Case-specific regulatory mappings.
        con.execute(
            'DELETE FROM standards_mappings WHERE case_id=?',
            (case_id,)
        )

        # Evidence provenance and passages.
        for document_id in documents:
            con.execute(
                'DELETE FROM source_provenance WHERE document_id=?',
                (document_id,)
            )

            con.execute(
                'DELETE FROM evidence_passages WHERE document_id=?',
                (document_id,)
            )

        # Investigation reviews and jobs.
        con.execute(
            'DELETE FROM investigation_reviews WHERE case_id=?',
            (case_id,)
        )
        con.execute(
            'DELETE FROM investigation_jobs WHERE case_id=?',
            (case_id,)
        )

        # Investigation and analysis results.
        con.execute(
            'DELETE FROM investigation_execution WHERE case_id=?',
            (case_id,)
        )
        con.execute(
            'DELETE FROM investigation_runs WHERE case_id=?',
            (case_id,)
        )
        con.execute(
            'DELETE FROM evidence_runs WHERE case_id=?',
            (case_id,)
        )
        con.execute(
            'DELETE FROM triage_runs WHERE case_id=?',
            (case_id,)
        )

        # Scenario sessions and uploaded evidence records.
        con.execute(
            'DELETE FROM scenario_sessions WHERE case_id=?',
            (case_id,)
        )

        for document_id in documents:
            con.execute(
                'DELETE FROM evidence_documents WHERE id=?',
                (document_id,)
            )

        # Remove case-specific audit history and the case itself.
        con.execute(
            'DELETE FROM audit WHERE case_id=?',
            (case_id,)
        )
        con.execute(
            'DELETE FROM cases WHERE id=?',
            (case_id,)
        )

    return {'success': True, 'deleted_case_id': case_id}


@app.patch('/api/cases/{case_id}')
def update_case(case_id: str, patch: CaseUpdate):
    with db() as con:
        existing = con.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail='Case not found')
        con.execute('UPDATE cases SET status=?, updated_at=? WHERE id=?', (patch.status, now(), case_id))
        record(con, case_id, 'case.status_changed', f'{existing["status"]} -> {patch.status}')
        return dict(con.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone())

@app.get('/api/audit')
def list_audit():
    with db() as con:
        return [dict(row) for row in con.execute('SELECT * FROM audit ORDER BY created_at DESC LIMIT 200')]

@app.get('/api/summary')
def summary():
    with db() as con:
        total = con.execute('SELECT COUNT(*) FROM cases').fetchone()[0]
        open_cases = con.execute("SELECT COUNT(*) FROM cases WHERE status != 'Resolved'").fetchone()[0]
        high = con.execute("SELECT COUNT(*) FROM cases WHERE priority = 'High' AND status != 'Resolved'").fetchone()[0]
        return {'total_cases': total, 'active_cases': open_cases, 'high_priority_open': high, 'evidence_items': con.execute('SELECT COUNT(*) FROM evidence_documents').fetchone()[0], 'agents_running': con.execute("SELECT COUNT(*) FROM investigation_jobs WHERE status='running'").fetchone()[0]}

# Protected local model management.
from .model_orchestrator.api import install as install_model_management
install_model_management(app)

# Register real LLM-backed intake triage and persistent analysis history.
from .triage import install as install_triage
install_triage(app, DB_PATH)

from .evidence import install as install_evidence
install_evidence(app, DB_PATH)

from .investigation import install as install_investigation
install_investigation(app, DB_PATH)

# Phase 7: persistent human review of advisory investigation outputs.
from .review import install as install_review
install_review(app, DB_PATH)

# Phase 8A: reviewer-attested policy source provenance
from .source_registry import install as install_source_registry
install_source_registry(app, DB_PATH)

from .research_api import install as install_research_api
install_research_api(app, DB_PATH)

# Authenticated, human-review-gated research evidence import.
from .research_import import install as install_research_import
install_research_import(app, DB_PATH)
from .standards_registry import install as install_standards_registry
install_standards_registry(app, DB_PATH)



# Phase 8C: collaborative, moderated global knowledge base
from .knowledge_base import install as install_knowledge_base
install_knowledge_base(app, DB_PATH)


# CIVITAS 0.4B: durable background investigation queue.
from .job_queue import install as install_job_queue
install_job_queue(app, DB_PATH)

# Auditable hypothetical scenario event sessions (separate from AI workflow).
from .scenario_sessions import install as install_scenario_sessions
install_scenario_sessions(app, DB_PATH)

# Question-first grounded research preview.
from .ask import install as install_ask
install_ask(app)

# Model relay shares the API authentication and configured Qwen router.
from .briefing import install as install_briefing
install_briefing(app)
