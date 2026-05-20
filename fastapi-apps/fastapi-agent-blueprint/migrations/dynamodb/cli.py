"""CLI entry point for DynamoDB migrations.

Usage:
    python -m migrations.dynamodb.cli --env local
    python -m migrations.dynamodb.cli --env dev
    python -m migrations.dynamodb.cli --env prod
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import boto3
except ImportError as exc:
    raise SystemExit(
        "[ERROR] Missing optional dependency 'boto3' for DynamoDB migrations. "
        "Install with: uv sync --extra aws"
    ) from exc

from dotenv import load_dotenv

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="DynamoDB table migrator")
    parser.add_argument(
        "--env",
        required=True,
        help="Environment name (loads _env/{env}.env)",
    )
    args = parser.parse_args()

    # Load environment variables
    env_file = PROJECT_ROOT / "_env" / f"{args.env}.env"
    if not env_file.exists():
        print(f"[ERROR] Environment file not found: {env_file}")
        sys.exit(1)

    load_dotenv(env_file, override=True)
    print(f"[INFO] Loaded environment from {env_file}")

    # Import after env is loaded so Settings picks up the values
    from src._core.config import settings

    if not settings.dynamodb_region:
        print("[SKIP] DynamoDB is not configured (DYNAMODB_REGION not set).")
        return

    # Create sync boto3 client
    client = boto3.client(
        "dynamodb",
        region_name=settings.dynamodb_region,
        aws_access_key_id=settings.dynamodb_access_key,
        aws_secret_access_key=settings.dynamodb_secret_key,
        endpoint_url=settings.dynamodb_endpoint_url,
    )

    # Scan for DynamoModel subclasses
    from migrations.dynamodb.scanner import scan_dynamo_models

    src_root = PROJECT_ROOT / "src"
    models = scan_dynamo_models(src_root)

    if not models:
        print("[INFO] No DynamoModel subclasses found.")
        return

    print(f"[INFO] Found {len(models)} DynamoDB model(s):")
    for model in models:
        print(f"  - {model.__name__} → {model.__dynamo_meta__.tablename}")

    # Migrate each model
    from migrations.dynamodb.migrator import DynamoDBMigrator

    migrator = DynamoDBMigrator(client)
    for model in models:
        print(f"\n[MIGRATE] {model.__name__}")
        migrator.migrate_model(model)

    print("\n[DONE] Migration complete.")


if __name__ == "__main__":
    main()
