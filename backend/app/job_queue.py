"""CIVITAS durable investigation queue.

Jobs are executed by a separate worker process.
Interrupted jobs require explicit human intervention.
"""
import argparse
import json
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from . import investigation

router = APIRouter()
DB_PATH = None


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    if DB_PATH is None:
        raise RuntimeError("Job queue not initialized")
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=30000")
    return db


def install(app, db_path):
    global DB_PATH
    DB_PATH = str(db_path)

    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS investigation_jobs (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id),
                status TEXT NOT NULL CHECK(
                    status IN (
                        'queued', 'running', 'completed',
                        'failed', 'interrupted'
                    )
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                worker_id TEXT,
                heartbeat_at TEXT,
                result_id TEXT,
                error_type TEXT
            )
        """)

        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                one_active_investigation_job
            ON investigation_jobs(case_id)
            WHERE status IN ('queued', 'running')
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS investigation_jobs_status_idx
            ON investigation_jobs(status, created_at)
        """)

        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                one_globally_running_investigation
            ON investigation_jobs((1))
            WHERE status='running'
        """)

        db.commit()

    # Register each job endpoint directly through FastAPI.
    # Avoid relying on the application's router wrapper.
    for route in router.routes:
        route_path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)

        if not route_path or not methods:
            continue

        existing = [
            item
            for item in app.routes
            if getattr(item, "path", None) == route_path
            and bool(set(methods) & set(getattr(item, "methods", set())))
        ]

        if existing:
            continue

        app.add_api_route(
            route_path,
            route.endpoint,
            methods=sorted(methods),
            status_code=route.status_code,
            response_model=route.response_model,
            name=route.name,
        )


def public_job(row):
    job = dict(row)
    job["queue_position"] = (
        queue_position(job["id"])
        if job["status"] == "queued"
        else None
    )
    return job


@router.post(
    "/api/cases/{case_id}/investigate/async",
    status_code=202
)
def enqueue(case_id: str):
    with connect() as db:
        investigation.get_case(db, case_id)

        # BEGIN IMMEDIATE serializes competing job submissions.
        db.execute("BEGIN IMMEDIATE")

        active = db.execute("""
            SELECT * FROM investigation_jobs
            WHERE case_id=? AND status IN ('queued','running')
            LIMIT 1
        """, (case_id,)).fetchone()

        if active:
            db.commit()
            return public_job(active)

        job_id = str(uuid4())
        stamp = now()

        db.execute("""
            INSERT INTO investigation_jobs
            (id, case_id, status, created_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?)
        """, (job_id, case_id, stamp, stamp))

        db.commit()

        return public_job(db.execute(
            "SELECT * FROM investigation_jobs WHERE id=?",
            (job_id,)
        ).fetchone())


@router.get("/api/cases/{case_id}/jobs")
def list_jobs(case_id: str):
    with connect() as db:
        investigation.get_case(db, case_id)

        return [
            public_job(row)
            for row in db.execute("""
                SELECT * FROM investigation_jobs
                WHERE case_id=?
                ORDER BY created_at DESC
                LIMIT 50
            """, (case_id,))
        ]


@router.get("/api/cases/{case_id}/jobs/{job_id}")
def get_job(case_id: str, job_id: str):
    with connect() as db:
        investigation.get_case(db, case_id)

        row = db.execute("""
            SELECT * FROM investigation_jobs
            WHERE id=? AND case_id=?
        """, (job_id, case_id)).fetchone()

        if row is None:
            raise HTTPException(404, "Job not found")

        return public_job(row)


def queue_position(job_id):
    """Return a queued job's 1-based position among waiting jobs."""
    with connect() as db:
        rows = db.execute("""
            SELECT id
            FROM investigation_jobs
            WHERE status='queued'
            ORDER BY created_at, id
        """).fetchall()
    for index, row in enumerate(rows, start=1):
        if row["id"] == job_id:
            return index
    return None


def claim(worker_id):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")

        # A single running investigation is allowed across all cases.
        # BEGIN IMMEDIATE serializes competing workers.
        running = db.execute("""
            SELECT id FROM investigation_jobs
            WHERE status='running'
            LIMIT 1
        """).fetchone()

        if running is not None:
            db.commit()
            return None

        row = db.execute("""
            SELECT * FROM investigation_jobs
            WHERE status='queued'
            ORDER BY created_at, id
            LIMIT 1
        """).fetchone()

        if row is None:
            db.commit()
            return None

        stamp = now()

        db.execute("""
            UPDATE investigation_jobs
            SET status='running',
                worker_id=?,
                heartbeat_at=?,
                updated_at=?
            WHERE id=? AND status='queued'
        """, (worker_id, stamp, stamp, row["id"]))

        db.commit()
        return dict(row)


def finish(job_id, worker_id, status, result_id=None, error_type=None):
    if status not in ("completed", "failed"):
        raise ValueError("Invalid terminal job status")

    with connect() as db:
        db.execute("""
            UPDATE investigation_jobs
            SET status=?,
                result_id=?,
                error_type=?,
                updated_at=?
            WHERE id=? AND worker_id=? AND status='running'
        """, (
            status, result_id, error_type,
            now(), job_id, worker_id
        ))
        db.commit()



def heartbeat(job_id, worker_id):
    """Refresh only the job still owned by this worker."""
    with connect() as db:
        stamp = now()
        cursor = db.execute("""
            UPDATE investigation_jobs
            SET heartbeat_at=?, updated_at=?
            WHERE id=? AND worker_id=? AND status='running'
        """, (stamp, stamp, job_id, worker_id))
        db.commit()
        return cursor.rowcount == 1


def heartbeat_loop(job_id, worker_id, stop_event):
    """Keep job liveness visible during blocking inference."""
    while not stop_event.wait(5):
        try:
            if not heartbeat(job_id, worker_id):
                return
        except sqlite3.Error as exc:
            print(
                f"Heartbeat warning for {job_id}: "
                f"{type(exc).__name__}",
                flush=True
            )


def run_one(worker_id):
    job = claim(worker_id)

    if job is None:
        return False

    stop_heartbeat = threading.Event()
    heartbeat_thread = threading.Thread(
        target=heartbeat_loop,
        args=(job["id"], worker_id, stop_heartbeat),
        daemon=True,
        name=f"civitas-heartbeat-{job['id'][:8]}"
    )
    heartbeat_thread.start()

    try:
        try:
            # Reuse the existing real six-stage workflow.
            result = investigation.run_workflow(job["case_id"])
        except Exception as exc:
            finish(
                job["id"], worker_id,
                "failed", error_type=type(exc).__name__
            )
            # Worker logs must not disclose exception messages, prompts,
            # model output or evidence through chained tracebacks.
            print(
                f"Job {job['id']} failed: {type(exc).__name__}",
                flush=True
            )
        else:
            finish(
                job["id"], worker_id,
                "completed", result_id=result["id"]
            )
            print(f"Job {job['id']} completed", flush=True)
    finally:
        # Never leak a heartbeat thread if finishing the job raises.
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=10)
    return True


def stale_running_jobs(threshold_seconds=90, at=None):
    """Read-only stale-heartbeat diagnostic; never assume a worker is dead.

    A heartbeat can be delayed by a busy database or a paused process.
    Operators must stop/check workers before invoking explicit recovery.
    """
    if threshold_seconds <= 0:
        raise ValueError("threshold_seconds must be positive")
    reference = at or datetime.now(timezone.utc)
    cutoff = (reference - timedelta(seconds=threshold_seconds)).isoformat()
    with connect() as db:
        rows = db.execute("""
            SELECT id, case_id, worker_id, heartbeat_at, updated_at
            FROM investigation_jobs
            WHERE status='running'
              AND (heartbeat_at IS NULL OR heartbeat_at < ?)
            ORDER BY created_at, id
        """, (cutoff,)).fetchall()
    return [dict(row) for row in rows]


def recover_stale_jobs(threshold_seconds=90, workers_stopped=False):
    """Operator-gated, transactional stale recovery; never requeue jobs.

    Workers must be stopped externally first. Stale timestamps alone cannot
    distinguish a crashed worker from a paused or overloaded live worker.
    """
    if not workers_stopped:
        raise ValueError("Confirm all investigation workers are stopped")
    if threshold_seconds <= 0:
        raise ValueError("threshold_seconds must be positive")
    stamp = now()
    cutoff = (datetime.now(timezone.utc) -
              timedelta(seconds=threshold_seconds)).isoformat()
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        stale = db.execute("""
            SELECT id, case_id FROM investigation_jobs
            WHERE status='running'
              AND (heartbeat_at IS NULL OR heartbeat_at < ?)
        """, (cutoff,)).fetchall()
        case_ids = sorted({row['case_id'] for row in stale})
        if stale:
            db.executemany("""
                UPDATE investigation_jobs
                SET status='interrupted', error_type='WorkerInterrupted',
                    updated_at=?
                WHERE id=? AND status='running'
            """, [(stamp, row['id']) for row in stale])
        # Do not touch executions for healthy jobs or unrelated cases.
        for case_id in case_ids:
            db.execute("""
                UPDATE investigation_execution
                SET status='failed', error_type='WorkerInterrupted',
                    updated_at=?
                WHERE case_id=? AND status='running'
            """, (stamp, case_id))
        db.commit()
    return len(stale)


def mark_interrupted_jobs():
    """Explicit operator recovery after confirming workers are stopped.

    Does not replay model calls or investigation side effects.
    """
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")

        count = db.execute("""
            UPDATE investigation_jobs
            SET status='interrupted',
                updated_at=?,
                error_type='WorkerInterrupted'
            WHERE status='running'
        """, (now(),)).rowcount

        # Release orphaned investigation locks as well.
        db.execute("""
            UPDATE investigation_execution
            SET status='failed',
                error_type='WorkerInterrupted',
                updated_at=?
            WHERE status='running'
        """, (now(),))

        db.commit()
        return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--recover",
        action="store_true",
        help="Mark interrupted jobs after all old workers are stopped"
    )
    parser.add_argument(
        "--recover-stale",
        action="store_true",
        help="Recover only stale jobs after confirming every worker is stopped"
    )
    parser.add_argument(
        "--workers-stopped",
        action="store_true",
        help="Explicit acknowledgment required for --recover-stale"
    )
    parser.add_argument(
        "--stale-report",
        action="store_true",
        help="List stale running jobs without modifying jobs or locks"
    )
    parser.add_argument(
        "--stale-seconds",
        type=int,
        default=90,
        help="Heartbeat age threshold for --stale-report (default: 90)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued job"
    )
    args = parser.parse_args()

    # Importing main initializes the same database and agent modules
    # as the API server.
    from . import main as api_main

    install_if_needed = DB_PATH is None
    if install_if_needed:
        install(api_main.app, api_main.DB_PATH)

    if args.recover_stale:
        if not args.workers_stopped:
            parser.error("--recover-stale requires --workers-stopped; stop all workers first")
        print("Stale jobs interrupted:",
              recover_stale_jobs(args.stale_seconds, workers_stopped=True))
        return

    if args.stale_report:
        print(json.dumps({
            "stale_running_jobs": stale_running_jobs(args.stale_seconds),
            "warning": "Stale heartbeat does not prove worker death; do not recover while a worker may still be running."
        }, indent=2))
        return

    if args.recover:
        print(
            "Interrupted jobs marked:",
            mark_interrupted_jobs()
        )
        return

    worker_id = str(uuid4())
    print("CIVITAS worker started:", worker_id, flush=True)

    while True:
        processed = run_one(worker_id)

        if args.once:
            return

        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    main()
