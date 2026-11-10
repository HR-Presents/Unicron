"""Real, auditable intake triage. No synthetic agent results."""
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .model_orchestrator.client import completion

router = APIRouter()
DB_PATH = None  # supplied by main.py at registration
MODEL = os.getenv('CIVITAS_LLM_MODEL', 'unsloth/Qwen3-1.7B-GGUF:Q4_K_M')
BASE_URL = os.getenv('CIVITAS_LLM_BASE_URL', 'http://127.0.0.1:42516/v1').rstrip('/')

class TriageResult(BaseModel):
    classification: str = Field(min_length=2, max_length=180)
    recommended_priority: str = Field(pattern='^(Low|Medium|High)$')
    rationale: str = Field(min_length=3, max_length=2000)
    missing_evidence: list[str] = Field(max_length=8)
    immediate_actions: list[str] = Field(max_length=6)


def connect():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    return con


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def parse_json(content):
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.S).strip()
    content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content, flags=re.I).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for i, char in enumerate(content):
            if char == '{':
                try:
                    obj, _ = decoder.raw_decode(content[i:])
                    return obj
                except json.JSONDecodeError:
                    continue
        raise ValueError('Model did not return valid JSON')


def infer(case):
    system = ('You are CIVITAS Intake & Triage, a decision-support assistant, not an authority. '
              'Assess only the supplied complaint. Never invent evidence, legislation, or official actions. '
              'Return ONLY a JSON object with keys: classification (string), recommended_priority '
              '(Low|Medium|High), rationale (string), missing_evidence (array of strings), '
              'immediate_actions (array of strings). Make actions recommendations for human review. '
              'If evidence is missing, explicitly say so. No markdown or thinking.')
    user = json.dumps({k: case[k] for k in ('title','summary','domain','priority')}) + '\n/no_think'
    payload = {'model': MODEL, 'messages': [{'role':'system','content':system}, {'role':'user','content':user}],
               'temperature': 0.1, 'max_tokens': 550, 'stream': False,
               'chat_template_kwargs': {'enable_thinking': False}}
    try:
        data = completion(payload, timeout=120)
        content = data['choices'][0]['message']['content']
        result = TriageResult.model_validate(parse_json(content))
        return result.model_dump(), data.get('model', MODEL)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=503, detail=f'Local LLM unavailable: {type(exc).__name__}') from exc
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail=f'Invalid model output: {str(exc)[:180]}') from exc


@router.post('/api/cases/{case_id}/triage')
def run_triage(case_id: str):
    with connect() as con:
        case = con.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
        if case is None:
            raise HTTPException(status_code=404, detail='Case not found')
        case = dict(case)
    # Do not hold SQLite locks while model is generating.
    result, model = infer(case)
    stamp = utc_now()
    analysis_id = str(uuid4())
    with connect() as con:
        con.execute('INSERT INTO triage_runs (id,case_id,model,result_json,created_at) VALUES (?,?,?,?,?)',
                    (analysis_id, case_id, model, json.dumps(result), stamp))
        con.execute('INSERT INTO audit (id,case_id,action,detail,created_at) VALUES (?,?,?,?,?)',
                    (str(uuid4()),case_id,'agent.triage_completed',f'Intake & Triage completed; run={analysis_id}; model={model}',stamp))
        con.commit()
    return {'id':analysis_id,'case_id':case_id,'agent':'Intake & Triage','model':model,
            'created_at':stamp,'result':result,'human_review_required':True}


@router.get('/api/cases/{case_id}/triage')
def triage_history(case_id: str):
    with connect() as con:
        if con.execute('SELECT 1 FROM cases WHERE id=?', (case_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail='Case not found')
        rows = con.execute('SELECT * FROM triage_runs WHERE case_id=? ORDER BY created_at DESC', (case_id,)).fetchall()
    return [{'id':r['id'],'case_id':r['case_id'],'agent':'Intake & Triage','model':r['model'],
             'created_at':r['created_at'],'result':json.loads(r['result_json']), 'human_review_required':True} for r in rows]


def install(app, db_path):
    global DB_PATH
    DB_PATH = str(db_path)
    with connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS triage_runs (
          id TEXT PRIMARY KEY, case_id TEXT NOT NULL, model TEXT NOT NULL,
          result_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(id))''')
        con.commit()
    app.include_router(router)
