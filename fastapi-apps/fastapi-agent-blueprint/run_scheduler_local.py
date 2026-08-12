"""Local runner for the Taskiq scheduler process (#206 Phase 2).

Mirrors ``run_worker_local.py``: loads the chosen ``_env/{env}.env`` file then
hands off to Taskiq's scheduler CLI. The scheduler reads
``schedule=[{"cron": "..."}]`` labels from registered tasks and enqueues them
to the broker on time.

Usage::

    python run_scheduler_local.py --env local
    # or
    make scheduler
"""

import argparse
import asyncio

from dotenv import load_dotenv

# Imported from the modules that *define* them, which is also what taskiq's own
# `SchedulerCMD` does. `taskiq.cli.scheduler.cmd` re-exports neither symbol via
# `__all__`, so importing from there reaches through a py.typed package's private
# surface — the kind of import that breaks silently on an upstream refactor.
from taskiq.cli.scheduler.args import SchedulerArgs
from taskiq.cli.scheduler.run import run_scheduler


def main() -> None:
    scheduler_args = SchedulerArgs(
        scheduler="src._apps.worker.scheduler:scheduler",
        modules=["src._apps.worker.scheduler"],
    )
    # `asyncio.run`, because `run_scheduler` is a coroutine function — unlike
    # `run_worker`, which is sync. This file says it mirrors `run_worker_local.py`
    # and did so literally, calling the coroutine and dropping it: `make scheduler`
    # emitted "coroutine 'run_scheduler' was never awaited" and exited 0 without
    # ever scheduling anything, so `audit_cleanup_task` never fired from the path
    # the docs point at. taskiq's own `SchedulerCMD.exec` wraps it the same way.
    asyncio.run(run_scheduler(scheduler_args))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    args = parser.parse_args()

    load_dotenv(dotenv_path=f"_env/{args.env}.env", override=True)

    main()
