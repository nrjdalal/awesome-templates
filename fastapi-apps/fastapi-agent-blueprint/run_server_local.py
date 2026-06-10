import argparse
import os

import uvicorn
from dotenv import load_dotenv

# import subprocess


def main():
    # ``log_config=None`` prevents uvicorn from installing its own
    # ``dictConfig`` at startup, which would clobber the structlog
    # ``ProcessorFormatter`` handlers configured in ``bootstrap_app`` (#9).
    # ``PORT`` env override (default 8001) lets a second instance run alongside
    # the primary dev server — e.g. to preview an alternate ADMIN_THEME_PALETTE.
    uvicorn.run(
        "src._apps.server.app:app",
        reload=True,
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8001")),
        log_config=None,
    )
    # subprocess.run([
    #     "gunicorn",
    #     "src.apps.monolith.app:app",
    #     "-k", "uvicorn.workers.UvicornWorker",
    #     "-w", "1",
    #     "-b", "0.0.0.0:8000"
    # ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    args = parser.parse_args()

    load_dotenv(dotenv_path=f"_env/{args.env}.env", override=True)

    main()
