"""CLI entry point for S3 Vectors index migrations.

Usage:
    python -m migrations.s3vectors.cli --env local
    python -m migrations.s3vectors.cli --env dev --list
    python -m migrations.s3vectors.cli --env prod --cleanup
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import boto3
except ImportError as exc:
    raise SystemExit(
        "[ERROR] Missing optional dependency 'boto3' for S3 Vectors migrations. "
        "Install with: uv sync --extra aws"
    ) from exc

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="S3 Vectors index migrator")
    parser.add_argument(
        "--env",
        required=True,
        help="Environment name (loads _env/{env}.env)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing indexes and exit",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete orphaned indexes not defined in code",
    )
    args = parser.parse_args()

    env_file = PROJECT_ROOT / "_env" / f"{args.env}.env"
    if not env_file.exists():
        print(f"[ERROR] Environment file not found: {env_file}")
        sys.exit(1)

    load_dotenv(env_file, override=True)
    print(f"[INFO] Loaded environment from {env_file}")

    from src._core.config import settings

    if not settings.s3vectors_region:
        print("[SKIP] S3 Vectors is not configured (S3VECTORS_REGION not set).")
        return

    client = boto3.client(
        "s3vectors",
        region_name=settings.s3vectors_region,
        aws_access_key_id=settings.s3vectors_access_key,
        aws_secret_access_key=settings.s3vectors_secret_key,
    )

    from migrations.s3vectors.migrator import S3VectorMigrator
    from migrations.s3vectors.scanner import scan_s3vector_models

    migrator = S3VectorMigrator(client, settings.s3vectors_bucket_name)

    if args.list:
        indexes = migrator.list_indexes()
        if not indexes:
            print("[INFO] No indexes found.")
            return
        print(f"[INFO] {len(indexes)} index(es):")
        for idx in indexes:
            print(f"  - {idx.get('indexName')}")
        return

    src_root = PROJECT_ROOT / "src"
    models = scan_s3vector_models(src_root)

    if not models:
        print("[INFO] No VectorModel subclasses found.")
        return

    print(f"[INFO] Found {len(models)} vector model(s):")
    for model in models:
        print(f"  - {model.__name__} -> {model.__vector_meta__.index_name}")

    for model in models:
        print(f"\n[MIGRATE] {model.__name__}")
        migrator.migrate_model(model)

    if args.cleanup:
        print("\n[CLEANUP] Checking for orphaned indexes...")
        deleted = migrator.cleanup_orphaned_indexes(models)
        print(f"[CLEANUP] Deleted {deleted} orphaned index(es).")

    print("\n[DONE] Migration complete.")


if __name__ == "__main__":
    main()
