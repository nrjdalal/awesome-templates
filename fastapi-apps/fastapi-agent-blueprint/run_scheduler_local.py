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

from dotenv import load_dotenv
from taskiq.cli.scheduler.cmd import SchedulerArgs, run_scheduler


def main() -> None:
    scheduler_args = SchedulerArgs(
        scheduler="src._apps.worker.scheduler:scheduler",
        modules=["src._apps.worker.scheduler"],
    )
    run_scheduler(scheduler_args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    args = parser.parse_args()

    load_dotenv(dotenv_path=f"_env/{args.env}.env", override=True)

    main()
