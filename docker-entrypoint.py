#!/usr/bin/env python3
"""Container entrypoint: run the API server and the standalone scheduler
in a single container, so scheduled analyses trigger out of the box
without extra services (no Redis required — the job store stays
in-process, reports persist to the shared SQLite database).

To run only one process, override the container command, e.g.:
    docker run ... <image> uv run --no-sync tradingagents-api
"""
from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

ENTRYPOINTS = ("tradingagents-api", "tradingagents-scheduler")

# uv sync installs the project into /app/.venv; calling the venv binaries
# directly keeps signals and exit codes on the real server process.  Fall
# back to `uv run` if the layout ever changes.
_VENV_BIN = Path("/app/.venv/bin")


def _resolve(name: str) -> list[str]:
    exe = _VENV_BIN / name
    return [str(exe)] if exe.exists() else ["uv", "run", "--no-sync", name]


def supervise(commands: Sequence[Sequence[str]]) -> int:
    """Run all commands; exit with the first one's exit code, stopping the rest."""
    procs = [subprocess.Popen(list(cmd)) for cmd in commands]

    def _forward_stop(signum: int, _frame: object) -> None:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()

    signal.signal(signal.SIGTERM, _forward_stop)
    signal.signal(signal.SIGINT, _forward_stop)

    exit_code = 0
    while True:
        codes = [proc.poll() for proc in procs]
        finished = next((c for c in codes if c is not None), None)
        if finished is not None:
            exit_code = finished
            break
        time.sleep(0.5)

    for proc in procs:
        if proc.poll() is None:
            proc.terminate()
    for proc in procs:
        proc.wait()

    if exit_code < 0:  # killed by signal N -> conventional 128 + N
        exit_code = 128 - exit_code
    return exit_code


def main() -> int:
    return supervise([_resolve(name) for name in ENTRYPOINTS])


if __name__ == "__main__":
    sys.exit(main())
