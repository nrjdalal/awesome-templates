from typing import ClassVar

import pytest

from src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_model import (
    DynamoModel,
    DynamoModelMeta,
    GSIDefinition,
)


class SampleModel(DynamoModel):
    __dynamo_meta__: ClassVar[DynamoModelMeta] = DynamoModelMeta(
        tablename="test_chat_room",
        partition_key_name="PK",
        sort_key_name="SK",
        gsi=[
            GSIDefinition(
                index_name="GSI1",
                partition_key_name="GSI1PK",
                sort_key_name="GSI1SK",
            )
        ],
    )

    org_id: str
    room_id: str
    room_name: str
    member_count: int = 0

    def get_partition_key(self) -> str:
        return "ORG#" + self.org_id

    def get_sort_key(self) -> str:
        return "ROOM#" + self.room_id

    def get_gsi_GSI1_pk(self) -> str:
        return "ORG#" + self.org_id + "#ROOM#" + self.room_id

    def get_gsi_GSI1_sk(self) -> str:
        return "NAME#" + self.room_name


class SimpleKeyModel(DynamoModel):
    __dynamo_meta__: ClassVar[DynamoModelMeta] = DynamoModelMeta(
        tablename="test_simple",
        partition_key_name="id",
    )

    id: str
    value: str

    def get_partition_key(self) -> str:
        return self.id


class TestDynamoModelSerialization:
    def test_to_dynamodb_includes_pk_sk(self):
        model = SampleModel(org_id="org1", room_id="room1", room_name="General")
        item = model.to_dynamodb()

        assert item["PK"] == {"S": "ORG#org1"}
        assert item["SK"] == {"S": "ROOM#room1"}

    def test_to_dynamodb_includes_gsi_keys(self):
        model = SampleModel(org_id="org1", room_id="room1", room_name="General")
        item = model.to_dynamodb()

        assert item["GSI1PK"] == {"S": "ORG#org1#ROOM#room1"}
        assert item["GSI1SK"] == {"S": "NAME#General"}

    def test_to_dynamodb_includes_data_fields(self):
        model = SampleModel(
            org_id="org1",
            room_id="room1",
            room_name="General",
            member_count=5,
        )
        item = model.to_dynamodb()

        assert item["room_name"] == {"S": "General"}
        assert item["member_count"] == {"N": "5"}

    def test_from_dynamodb_roundtrip(self):
        original = SampleModel(
            org_id="org1",
            room_id="room1",
            room_name="General",
            member_count=5,
        )
        serialized = original.to_dynamodb()
        restored = SampleModel.from_dynamodb(serialized)

        assert restored.org_id == "org1"
        assert restored.room_id == "room1"
        assert restored.room_name == "General"
        assert restored.member_count == 5

    def test_simple_key_model_no_sort_key(self):
        model = SimpleKeyModel(id="abc", value="hello")
        item = model.to_dynamodb()

        assert item["id"] == {"S": "abc"}
        assert "SK" not in item

    def test_none_values_excluded(self):
        model = SimpleKeyModel(id="abc", value="hello")
        item = model.to_dynamodb()
        # All values should be present (no None fields in this model)
        assert len(item) == 2  # id, value

    def test_float_converted_to_decimal(self):
        """float should be converted to Decimal for DynamoDB Number type."""

        class FloatModel(DynamoModel):
            __dynamo_meta__: ClassVar[DynamoModelMeta] = DynamoModelMeta(
                tablename="test_float", partition_key_name="id"
            )
            id: str
            score: float

            def get_partition_key(self) -> str:
                return self.id

        model = FloatModel(id="1", score=3.14)
        item = model.to_dynamodb()
        assert item["score"] == {"N": "3.14"}

        restored = FloatModel.from_dynamodb(item)
        assert abs(restored.score - 3.14) < 0.001


class TestDynamoModelKeyGeneration:
    def test_get_partition_key(self):
        model = SampleModel(org_id="org1", room_id="room1", room_name="General")
        assert model.get_partition_key() == "ORG#org1"

    def test_get_sort_key(self):
        model = SampleModel(org_id="org1", room_id="room1", room_name="General")
        assert model.get_sort_key() == "ROOM#room1"

    def test_get_gsi_keys(self):
        model = SampleModel(org_id="org1", room_id="room1", room_name="General")
        gsi_keys = model.get_gsi_keys()
        assert gsi_keys["GSI1PK"] == "ORG#org1#ROOM#room1"
        assert gsi_keys["GSI1SK"] == "NAME#General"

    def test_not_implemented_without_override(self):
        class BadModel(DynamoModel):
            __dynamo_meta__: ClassVar[DynamoModelMeta] = DynamoModelMeta(
                tablename="test", partition_key_name="PK"
            )
            name: str

        model = BadModel(name="test")
        with pytest.raises(NotImplementedError):
            model.get_partition_key()
