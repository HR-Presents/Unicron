import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

from app import job_queue


def test_only_one_investigation_can_run_globally(tmp_path, monkeypatch):
    db_path = tmp_path / "queue.sqlite3"
    monkeypatch.setattr(job_queue, "DB_PATH", str(db_path))

    with sqlite3.connect(db_path) as db:
        db.execute("""
            CREATE TABLE investigation_jobs (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                worker_id TEXT,
                heartbeat_at TEXT,
                result_id TEXT,
                error_type TEXT
            )
        """)
        for number in range(2):
            db.execute("""
                INSERT INTO investigation_jobs
                (id, case_id, status, created_at, updated_at)
                VALUES (?, ?, 'queued', ?, ?)
            """, (
                f"job-{number}",
                f"case-{number}",
                f"2026-11-08T00:00:0{number}+00:00",
                f"2026-11-08T00:00:0{number}+00:00",
            ))
        db.commit()

    barrier = threading.Barrier(2)

    def claim(worker):
        barrier.wait(timeout=5)
        return job_queue.claim(worker)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(claim, f"worker-{number}")
            for number in range(2)
        ]
        results = [future.result(timeout=10) for future in futures]

    assert sum(result is not None for result in results) == 1

    with sqlite3.connect(db_path) as db:
        statuses = dict(
            db.execute("SELECT status, COUNT(*) FROM investigation_jobs GROUP BY status")
        )

    assert statuses == {"queued": 1, "running": 1}
