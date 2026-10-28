#!/usr/bin/env python3
"""Launch both local services; stop both with Ctrl+C. No external services enabled."""
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    python = os.environ.get('AURUM_PYTHON')
    if python:
        # Child services use a different working directory.
        python = os.path.abspath(os.path.expanduser(python)) if os.path.dirname(python) else (shutil.which(python) or python)
    if not python:
        local = ROOT / 'backend' / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        python = str(local) if local.exists() else sys.executable
    npm = shutil.which('npm')
    if not npm or not (ROOT / 'frontend/node_modules').exists():
        sys.exit('Frontend dependencies missing. Run: make setup')
    check = subprocess.run([python, '-c', 'import fastapi, uvicorn, sqlalchemy, pydantic_settings, httpx'], capture_output=True)
    if check.returncode:
        sys.exit('Backend dependencies missing. Run: make setup')
    for port in (8000, 5173):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                sys.exit(f'Port {port} is unavailable. Stop the service using it before starting Aurum.')
    env_path = ROOT / 'backend/.env'
    if not env_path.exists():
        shutil.copyfile(ROOT / 'backend/.env.example', env_path)
    children = []

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        children.append(subprocess.Popen([python, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], cwd=ROOT/'backend', env=env, start_new_session=os.name != 'nt'))
        children.append(subprocess.Popen([npm, 'run', 'dev', '--', '--port', '5173', '--strictPort'], cwd=ROOT/'frontend', env=env, start_new_session=os.name != 'nt'))
        ready = False
        deadline = time.monotonic()+30
        while all(child.poll() is None for child in children):
            if not ready:
                try:
                    for url in ('http://127.0.0.1:8000/api/health','http://127.0.0.1:5173/'):
                        with urlopen(url, timeout=1) as response:
                            if response.status != 200:
                                raise OSError('Not ready')
                    print('\nAurum is ready: http://127.0.0.1:5173/\nAPI docs: http://127.0.0.1:8000/docs\nPress Ctrl+C to stop both services.\n', flush=True)
                    ready = True
                except OSError:
                    if time.monotonic()>deadline:
                        raise RuntimeError('Services did not become ready within 30 seconds. See startup output above.')
            time.sleep(0.5)
        if any(child.poll() not in (None,0) for child in children):
            raise RuntimeError('A service exited unexpectedly. See output above.')
    except KeyboardInterrupt:
        print('\nStopping Aurum…', flush=True)
    finally:
        for child in children:
            if child.poll() is None:
                if os.name == 'nt':
                    child.terminate()
                else:
                    os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                if os.name == 'nt':
                    child.kill()
                else:
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait()


if __name__ == '__main__':
    main()
