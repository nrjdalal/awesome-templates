import argparse

from dotenv import load_dotenv
from taskiq.cli.worker.args import WorkerArgs
from taskiq.cli.worker.cmd import run_worker

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

    run_worker(worker_args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    args = parser.parse_args()

    load_dotenv(dotenv_path=f"_env/{args.env}.env", override=True)

    try:
        main()
    except InMemoryWorkerError as exc:
        raise SystemExit(f"\n{exc}\n") from exc
