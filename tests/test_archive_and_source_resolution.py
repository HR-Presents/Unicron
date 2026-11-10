import sqlite3
from pathlib import Path
import pytest
from fastapi import HTTPException
from backend.app.archive import evidence_archive_path
from backend.app import evidence, investigation


def source_db(path, status='verified'):
    with sqlite3.connect(path) as db:
        db.executescript('''
          CREATE TABLE evidence_documents (id TEXT,filename TEXT);
          CREATE TABLE evidence_passages (document_id TEXT,position INTEGER,content TEXT);
          CREATE TABLE source_provenance (document_id TEXT,document_title TEXT,authority TEXT,
            jurisdiction TEXT,official_url TEXT,source_type TEXT,verification_status TEXT,verified_at TEXT);
          INSERT INTO evidence_documents VALUES ('policy-doc','policy.pdf');
          INSERT INTO evidence_passages VALUES ('policy-doc',2,'Exact documentary passage.');
        ''')
        db.execute('INSERT INTO source_provenance VALUES (?,?,?,?,?,?,?,?)',
                   ('policy-doc','Policy title','Authority','UAE','https://example.gov/policy','policy',status,'2026-11-10'))


def test_archive_follows_existing_workspace_database_across_worktrees(tmp_path,monkeypatch):
    monkeypatch.delenv('CIVITAS_EVIDENCE_ARCHIVE_PATH',raising=False)
    workspace=tmp_path/'existing'/'workspace.sqlite3'
    assert evidence_archive_path(workspace)==workspace.parent/'civitas.sqlite3'


def test_explicit_archive_location_is_respected(tmp_path,monkeypatch):
    configured=tmp_path/'national material'/'archive.sqlite3'
    monkeypatch.setenv('CIVITAS_EVIDENCE_ARCHIVE_PATH',str(configured))
    assert evidence_archive_path(tmp_path/'other.sqlite3')==configured


def test_missing_archive_does_not_create_a_database(tmp_path,monkeypatch):
    monkeypatch.setattr(evidence,'DB_PATH',str(tmp_path/'workspace.sqlite3'))
    monkeypatch.delenv('CIVITAS_EVIDENCE_ARCHIVE_PATH',raising=False)
    result=evidence.search_shared_verified_evidence('personal data')
    assert result['archive_available'] is False
    assert result['results']==[]
    assert not (tmp_path/'civitas.sqlite3').exists()


def test_exact_verified_citation_resolves_and_revocation_is_respected(tmp_path,monkeypatch):
    database=tmp_path/'workspace.sqlite3'
    source_db(database)
    monkeypatch.setattr(evidence,'DB_PATH',str(database))
    monkeypatch.delenv('CIVITAS_EVIDENCE_ARCHIVE_PATH',raising=False)
    result=evidence.verified_source_passage('policy-doc',2)
    assert result['text']=='Exact documentary passage.'
    assert result['citation']=='policy-doc#p2'
    with sqlite3.connect(database) as db:db.execute("UPDATE source_provenance SET verification_status='rejected'")
    with pytest.raises(HTTPException) as failure:evidence.verified_source_passage('policy-doc',2)
    assert failure.value.status_code==404


def test_unverified_sources_cannot_be_promoted_by_source_lookup(tmp_path,monkeypatch):
    database=tmp_path/'workspace.sqlite3'
    source_db(database,'unverified')
    monkeypatch.setattr(evidence,'DB_PATH',str(database))
    with pytest.raises(HTTPException):evidence.verified_source_passage('policy-doc',2)
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT verification_status FROM source_provenance').fetchone()[0]=='unverified'


def test_synthesis_gets_policy_content_and_only_unflagged_supported_comparisons():
    policy={'result':{'relevant_excerpts':[{'citation':'doc#p1','verbatim_excerpt':'Policy passage.'}]}}
    benchmark={'result':{'ai_comparison_draft':{
        'comparisons':[{'observation':'A'},{'observation':'B'},{'observation':'C'}],
        'model_evidence_assessments':[{'claim_index':0,'verdict':'supported'},
                                      {'claim_index':1,'verdict':'supported'},
                                      {'claim_index':2,'verdict':'contradicted'}],
        'claim_risk_flags':[{'claim_index':0,'code':'unproven_legal_conflict'}]}}}
    result=investigation.synthesis_policy_context(policy,benchmark)
    assert result['policy_excerpts'][0]['text']=='Policy passage.'
    assert result['model_assessed_comparisons']==[{'observation':'B'}]
    assert result['excluded_comparison_count']==2
