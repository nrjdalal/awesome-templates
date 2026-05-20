import argparse

from dotenv import load_dotenv
from taskiq.cli.worker.args import WorkerArgs
from taskiq.cli.worker.cmd import run_worker


def main():
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

    main()
