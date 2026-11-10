#!/usr/bin/env python3
"""Export verified documentary passages to JSONL without changing the source DB."""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def export(database, output):
    database=Path(database).expanduser().resolve()
    output=Path(output).expanduser().resolve()
    manifest=output.with_suffix(output.suffix+'.manifest.json')
    if not database.is_file():
        raise ValueError('Source database does not exist')
    if output.exists() or manifest.exists():
        raise ValueError('Output already exists; choose a new filename')
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute('''SELECT p.document_id,p.position,p.content,d.filename,
            s.document_title,s.authority,s.jurisdiction,s.official_url,s.source_type,
            s.verification_status,s.verified_at
            FROM evidence_passages p JOIN evidence_documents d ON d.id=p.document_id
            JOIN source_provenance s ON s.document_id=d.id
            WHERE s.verification_status='verified'
              AND s.source_type IN ('policy','benchmark','guidance')
              AND TRIM(COALESCE(s.authority,''))!=''
              AND TRIM(COALESCE(s.jurisdiction,''))!=''
              AND TRIM(COALESCE(s.official_url,''))!=''
            ORDER BY p.document_id,p.position''').fetchall()
    records=[]
    for row in rows:
        item=dict(row)
        item['citation']=f"{item['document_id']}#p{item['position']}"
        item['text']=item.pop('content')
        item['passage_sha256']=hashlib.sha256(item['text'].encode()).hexdigest()
        records.append(item)
    content=''.join(json.dumps(item,ensure_ascii=False)+'\n' for item in records)
    details={'schema':'unicron.documentary-passages.v1',
             'created_at':datetime.now(timezone.utc).isoformat(),
             'passage_count':len(records),'document_count':len({item['document_id'] for item in records}),
             'sha256':hashlib.sha256(content.encode()).hexdigest(),
             'source_status':'verified provenance records; not a legal certification',
             'distribution_status':'local export only; no ITU upload or vector indexing performed',
             'licensing':'Source documents retain their original licensing and redistribution conditions.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as file:file.write(content)
    with manifest.open('x',encoding='utf-8') as file:json.dump(details,file,indent=2)
    return details


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True,help='Existing SQLite workspace or regulatory archive')
    parser.add_argument('--output',required=True,help='New JSONL file; existing files are not overwritten')
    args=parser.parse_args()
    try:print(json.dumps(export(args.database,args.output),indent=2))
    except (ValueError,sqlite3.Error,OSError) as error:raise SystemExit(str(error))

if __name__=='__main__':main()
