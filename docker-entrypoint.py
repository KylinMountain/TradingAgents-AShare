#!/usr/bin/env python3
"""Container entrypoint: run the API server and the standalone scheduler
in a single container, so scheduled analyses trigger out of the box
without extra services (no Redis required — the job store stays
in-process, reports persist to the shared SQLite database).

For split deployments, each container selects its role with an env var:
    TA_DISABLE_SCHEDULER=1  -> only the API server
    TA_DISABLE_API=1        -> only the scheduler
Never run two scheduler instances against the same database — that can
trigger duplicate analyses.  Setting both vars is a misconfiguration and
exits non-zero without starting anything.

To run only one process without env vars, override the container command:
    docker run ... <image> uv run --no-sync tradingagents-api
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

_ENTRYPOINTS = (
    ("tradingagents-api", "TA_DISABLE_API"),
    ("tradingagents-scheduler", "TA_DISABLE_SCHEDULER"),
)

_TRUTHY = {"1", "true", "yes", "on"}

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


def _enabled_entrypoints() -> list[str]:
    return [
        name
        for name, disable_env in _ENTRYPOINTS
        if os.getenv(disable_env, "").strip().lower() not in _TRUTHY
    ]


def main() -> int:
    commands = [_resolve(name) for name in _enabled_entrypoints()]
    if not commands:
        print(
            "TA_DISABLE_API and TA_DISABLE_SCHEDULER are both set; nothing to run.",
            file=sys.stderr,
        )
        return 2
    return supervise(commands)


if __name__ == "__main__":
    sys.exit(main())
