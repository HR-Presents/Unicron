#!/usr/bin/env python3
"""Restart an idle local workspace using its running API's private environment."""
import os
import signal
import sqlite3
import time
from pathlib import Path

WORKERS = {'app.worker', 'backend.app.worker', 'app.job_queue', 'backend.app.job_queue'}


def process_info(process):
    try:
        arguments = [part.decode() for part in (process / 'cmdline').read_bytes().split(b'\0') if part]
        return arguments, (process / 'cwd').resolve()
    except (OSError, UnicodeError):
        return [], None


def alive(pid):
    try:
        return '\nState:\tZ' not in Path(f'/proc/{pid}/status').read_text()
    except OSError:
        return False


def main():
    root = Path(__file__).resolve().parents[1]
    original = root.parent / 'UNICRON'
    apis = []
    workers = []
    frontends = []
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        arguments, cwd = process_info(process)
        if cwd == root and any(Path(arg).name == 'uvicorn' for arg in arguments):
            apis.append(process)
        if cwd in (root, original) and WORKERS.intersection(arguments):
            workers.append(process)
        if cwd == root / 'frontend' and any(Path(arg).name == 'vite' for arg in arguments):
            frontends.append(process)
    if len(apis) != 1:
        raise SystemExit('STOP: Expected exactly one running API in this checkout. Nothing stopped.')
    environment = dict(os.environ)
    for item in (apis[0] / 'environ').read_bytes().split(b'\0'):
        if b'=' in item:
            key, value = item.split(b'=', 1)
            environment[key.decode()] = value.decode()
    database = Path(environment.get('CIVITAS_DB_PATH', ''))
    if not database.is_absolute() or not database.is_file():
        raise SystemExit('STOP: Running API has no existing absolute database path. Nothing stopped.')
    if not environment.get('CIVITAS_API_KEY'):
        raise SystemExit('STOP: Existing API authentication was not found. Nothing stopped.')
    if not (root / '.venv/bin/python').is_file() or not (root / 'frontend/node_modules/.bin/vite').is_file():
        raise SystemExit('STOP: Python environment or frontend dependencies are missing. Nothing stopped.')
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        active = db.execute("SELECT id,status FROM investigation_jobs WHERE status IN ('queued','running')").fetchall()
    if active:
        raise SystemExit(f'STOP: Let these investigations finish before restarting: {active}')
    environment['PYTHONPATH'] = f'{root}:{root / "backend"}'
    environment['UNICRON_MODEL_VIA_BACKEND'] = '1'
    environment['UNICRON_API_TOKEN'] = environment['CIVITAS_API_KEY']
    processes = workers + apis + frontends
    for process in processes:
        try:
            os.kill(int(process.name), signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 10
    while any(alive(int(process.name)) for process in processes):
        if time.monotonic() >= deadline:
            raise SystemExit('STOP: An old service has not exited; no replacement started.')
        time.sleep(0.2)
    for process in Path('/proc').iterdir():
        if process.name.isdigit():
            arguments, cwd = process_info(process)
            if cwd in (root, original) and WORKERS.intersection(arguments):
                raise SystemExit('STOP: A worker was restarted by another supervisor. No duplicate started.')
    os.chdir(root)
    print('Restarting integrated API, worker and frontend with the existing database and credentials.', flush=True)
    os.execvpe('bash', ['bash', str(root / 'start.sh')], environment)


if __name__ == '__main__':
    main()
