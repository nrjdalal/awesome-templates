"""DynamoDB table migrator.

Creates tables and manages GSI changes based on DynamoModel definitions.
Uses sync boto3 (table creation is a one-time operation, async not needed).
"""

from __future__ import annotations

from typing import Any

try:
    from botocore.exceptions import ClientError
except ImportError as exc:
    raise SystemExit(
        "[ERROR] Missing optional dependency 'botocore' for DynamoDB migrations. "
        "Install with: uv sync --extra aws"
    ) from exc

from src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_model import (
    DynamoModel,
)


def _make_attr_def(name: str) -> dict[str, str]:
    return {"AttributeName": name, "AttributeType": "S"}


def _make_key_element(name: str, key_type: str) -> dict[str, str]:
    return {"AttributeName": name, "KeyType": key_type}


class DynamoDBMigrator:
    """Sync DynamoDB table manager (create / update GSI)."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def migrate_model(self, model_cls: type[DynamoModel]) -> None:
        """Create or update the table for a DynamoModel subclass."""
        meta = model_cls.__dynamo_meta__
        table_name = meta.tablename

        try:
            existing = self.client.describe_table(TableName=table_name)
            print("  [EXISTS] " + table_name)
            self._update_gsi(table_name, meta, existing["Table"])
            self._update_ttl(table_name, meta)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                self._create_table(table_name, meta)
            else:
                raise

    def _create_table(self, table_name: str, meta: Any) -> None:
        """Create a new DynamoDB table with PAY_PER_REQUEST billing."""
        key_schema = [_make_key_element(meta.partition_key_name, "HASH")]
        attr_defs = [_make_attr_def(meta.partition_key_name)]

        if meta.sort_key_name:
            key_schema.append(_make_key_element(meta.sort_key_name, "RANGE"))
            attr_defs.append(_make_attr_def(meta.sort_key_name))

        params: dict[str, Any] = {
            "TableName": table_name,
            "KeySchema": key_schema,
            "AttributeDefinitions": attr_defs,
            "BillingMode": "PAY_PER_REQUEST",
        }

        if meta.gsi:
            gsi_list = []
            existing_attr_names = {a["AttributeName"] for a in attr_defs}

            for gsi in meta.gsi:
                gsi_key_schema = [_make_key_element(gsi.partition_key_name, "HASH")]
                if gsi.partition_key_name not in existing_attr_names:
                    attr_defs.append(_make_attr_def(gsi.partition_key_name))
                    existing_attr_names.add(gsi.partition_key_name)

                if gsi.sort_key_name:
                    gsi_key_schema.append(_make_key_element(gsi.sort_key_name, "RANGE"))
                    if gsi.sort_key_name not in existing_attr_names:
                        attr_defs.append(_make_attr_def(gsi.sort_key_name))
                        existing_attr_names.add(gsi.sort_key_name)

                projection: dict[str, Any] = {"ProjectionType": gsi.projection_type}
                if gsi.projection_type == "INCLUDE" and gsi.non_key_attributes:
                    projection["NonKeyAttributes"] = gsi.non_key_attributes

                gsi_list.append(
                    {
                        "IndexName": gsi.index_name,
                        "KeySchema": gsi_key_schema,
                        "Projection": projection,
                    }
                )
            params["GlobalSecondaryIndexes"] = gsi_list

        self.client.create_table(**params)
        waiter = self.client.get_waiter("table_exists")
        waiter.wait(TableName=table_name)
        print("  [CREATED] " + table_name)

    def _update_gsi(self, table_name: str, meta: Any, table_desc: dict) -> None:
        """Compare existing GSIs with model definition and apply changes."""
        existing_gsi = {
            g["IndexName"]: g for g in table_desc.get("GlobalSecondaryIndexes", [])
        }
        desired_gsi = {g.index_name: g for g in meta.gsi}

        to_delete = set(existing_gsi) - set(desired_gsi)
        to_add = set(desired_gsi) - set(existing_gsi)

        for name in set(existing_gsi) & set(desired_gsi):
            if self._gsi_changed(existing_gsi[name], desired_gsi[name]):
                to_delete.add(name)
                to_add.add(name)

        for name in sorted(to_delete):
            print("    [DELETE GSI] " + name)
            self.client.update_table(
                TableName=table_name,
                GlobalSecondaryIndexUpdates=[{"Delete": {"IndexName": name}}],
            )
            self._wait_for_table(table_name)

        for name in sorted(to_add):
            gsi = desired_gsi[name]
            print("    [ADD GSI] " + name)

            gsi_key_schema = [_make_key_element(gsi.partition_key_name, "HASH")]
            gsi_attr_defs = [_make_attr_def(gsi.partition_key_name)]

            if gsi.sort_key_name:
                gsi_key_schema.append(_make_key_element(gsi.sort_key_name, "RANGE"))
                gsi_attr_defs.append(_make_attr_def(gsi.sort_key_name))

            projection: dict[str, Any] = {"ProjectionType": gsi.projection_type}
            if gsi.projection_type == "INCLUDE" and gsi.non_key_attributes:
                projection["NonKeyAttributes"] = gsi.non_key_attributes

            self.client.update_table(
                TableName=table_name,
                AttributeDefinitions=gsi_attr_defs,
                GlobalSecondaryIndexUpdates=[
                    {
                        "Create": {
                            "IndexName": name,
                            "KeySchema": gsi_key_schema,
                            "Projection": projection,
                        }
                    }
                ],
            )
            self._wait_for_table(table_name)

    def _update_ttl(self, table_name: str, meta: Any) -> None:
        """Enable TTL if configured on the model."""
        if not meta.ttl_attribute:
            return

        try:
            ttl_desc = self.client.describe_time_to_live(TableName=table_name)
            current = ttl_desc.get("TimeToLiveDescription", {})
            status = current.get("TimeToLiveStatus")
            if status in ("ENABLED", "ENABLING"):
                if current.get("AttributeName") == meta.ttl_attribute:
                    return

            self.client.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={
                    "Enabled": True,
                    "AttributeName": meta.ttl_attribute,
                },
            )
            print("    [TTL] Enabled on '" + meta.ttl_attribute + "'")
        except ClientError as e:
            msg = e.response["Error"]["Message"]
            print("    [TTL WARN] " + msg)

    def _wait_for_table(self, table_name: str) -> None:
        waiter = self.client.get_waiter("table_exists")
        waiter.wait(TableName=table_name)

    @staticmethod
    def _gsi_changed(existing: dict, desired: Any) -> bool:
        """Check if a GSI's KeySchema or ProjectionType has changed."""
        existing_keys = {
            (k["AttributeName"], k["KeyType"]) for k in existing["KeySchema"]
        }
        desired_keys = {(desired.partition_key_name, "HASH")}
        if desired.sort_key_name:
            desired_keys.add((desired.sort_key_name, "RANGE"))

        if existing_keys != desired_keys:
            return True

        existing_projection = existing["Projection"]["ProjectionType"]
        return existing_projection != desired.projection_type
