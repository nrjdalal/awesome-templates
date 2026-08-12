import argparse

from dotenv import load_dotenv
from taskiq.cli.worker.args import WorkerArgs

# The defining module, not the `cmd` shim — see run_scheduler_local.py.
from taskiq.cli.worker.run import run_worker

from src._apps.worker.guards import InMemoryWorkerError, ensure_worker_capable_broker


def main():
    # Imported here (after load_dotenv) so the broker is selected against the
    # chosen environment's BROKER_TYPE before we guard it.
    from src._apps.worker.broker import broker

    ensure_worker_capable_broker(broker)

    worker_args = WorkerArgs(
        broker="src._apps.worker.app:app",
        modules=["src._apps.worker.app"],
        reload=True,
    )

    # Propagated, not discarded: `run_worker` returns a status code and taskiq's
    # own `WorkerCMD.exec` returns it, so swallowing it made this runner exit 0
    # on a failed worker start. `SystemExit(None)` is still a 0 exit.
    raise SystemExit(run_worker(worker_args))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    args = parser.parse_args()

    load_dotenv(dotenv_path=f"_env/{args.env}.env", override=True)

    try:
        main()
    except InMemoryWorkerError as exc:
        raise SystemExit(f"\n{exc}\n") from exc
