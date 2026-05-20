"""S3 Vectors index migrator.

Creates and manages indexes based on VectorModel definitions.
Uses sync boto3 (index management is a one-time operation).

Adapted from proj-ai-courseware-backend S3VectorIndexMigrator,
following the blueprint's DynamoDBMigrator pattern.
"""

from __future__ import annotations

import time
from typing import Any

try:
    from botocore.exceptions import ClientError
except ImportError as exc:
    raise SystemExit(
        "[ERROR] Missing optional dependency 'botocore' for S3 Vectors migrations. "
        "Install with: uv sync --extra aws"
    ) from exc

from src._core.infrastructure.vectors.vector_model import (
    VectorModel,
    VectorModelMeta,
)


class S3VectorMigrator:
    """Sync S3 Vectors index manager (create / update / cleanup)."""

    def __init__(self, client: Any, bucket_name: str) -> None:
        self.client = client
        self.bucket_name = bucket_name

    def migrate_model(self, model_cls: type[VectorModel]) -> None:
        """Create or update the index for a VectorModel subclass."""
        meta = model_cls.__vector_meta__

        try:
            response = self.client.get_index(
                vectorBucketName=self.bucket_name,
                indexName=meta.index_name,
            )
            existing = response.get("index", {})
            print("  [EXISTS] " + meta.index_name)

            if self._index_needs_update(existing, meta):
                print("  [RECREATE] " + meta.index_name + " (schema changed)")
                self._delete_index(meta.index_name)
                time.sleep(5)
                self._create_index(meta)
            else:
                print("  [OK] No changes needed")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                self._create_index(meta)
            else:
                raise

    def list_indexes(self) -> list[dict[str, Any]]:
        """List all indexes in the bucket."""
        response = self.client.list_indexes(vectorBucketName=self.bucket_name)
        return response.get("indexes", [])

    def cleanup_orphaned_indexes(self, model_classes: list[type[VectorModel]]) -> int:
        """Delete indexes not defined in code."""
        defined = {m.__vector_meta__.index_name for m in model_classes}
        existing: set[str] = {
            name
            for idx in self.list_indexes()
            if (name := idx.get("indexName")) is not None
        }
        orphaned = existing - defined

        if not orphaned:
            print("  [OK] No orphaned indexes")
            return 0

        deleted = 0
        for name in sorted(orphaned):
            print("  [DELETE] Orphaned index: " + name)
            self._delete_index(name)
            deleted += 1
            time.sleep(2)

        return deleted

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_index(self, meta: VectorModelMeta) -> None:
        """Create a new S3 Vectors index."""
        params: dict[str, Any] = {
            "vectorBucketName": self.bucket_name,
            "indexName": meta.index_name,
            "dataType": meta.data_type,
            "dimension": meta.dimension,
            "distanceMetric": meta.distance_metric,
        }

        if meta.non_filter_fields:
            params["metadataConfiguration"] = {
                "nonFilterableMetadataKeys": meta.non_filter_fields
            }

        self.client.create_index(**params)
        print("  [CREATED] " + meta.index_name)

    def _delete_index(self, index_name: str) -> None:
        """Delete an index."""
        try:
            self.client.delete_index(
                vectorBucketName=self.bucket_name,
                indexName=index_name,
            )
            time.sleep(3)
        except ClientError as e:
            print("  [WARN] Delete failed for " + index_name + ": " + str(e))

    def _index_needs_update(
        self, existing: dict[str, Any], meta: VectorModelMeta
    ) -> bool:
        """Compare existing index with model definition."""
        if existing.get("dataType", "").lower() != meta.data_type.lower():
            print(
                "    dataType changed: "
                + str(existing.get("dataType"))
                + " -> "
                + meta.data_type
            )
            return True

        if existing.get("dimension", 0) != meta.dimension:
            print(
                "    dimension changed: "
                + str(existing.get("dimension"))
                + " -> "
                + str(meta.dimension)
            )
            return True

        if existing.get("distanceMetric", "").lower() != meta.distance_metric.lower():
            print(
                "    distanceMetric changed: "
                + str(existing.get("distanceMetric"))
                + " -> "
                + meta.distance_metric
            )
            return True

        existing_non_filter = set(
            existing.get("metadataConfiguration", {}).get(
                "nonFilterableMetadataKeys", []
            )
        )
        desired_non_filter = set(meta.non_filter_fields)
        if existing_non_filter != desired_non_filter:
            print("    nonFilterableMetadataKeys changed")
            return True

        return False
