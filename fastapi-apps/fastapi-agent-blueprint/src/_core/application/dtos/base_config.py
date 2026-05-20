from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

API_CONFIG = ConfigDict(
    extra="ignore",
    frozen=True,
    populate_by_name=True,
    loc_by_alias=True,
    alias_generator=to_camel,
    ser_json_timedelta="iso8601",
    ser_json_bytes="utf8",
)

INTERNAL_CONFIG = ConfigDict(
    extra="forbid",
    # frozen=False,
)

PAYLOAD_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
)


class BaseConfig(BaseModel):
    pass


class ApiConfig(BaseConfig):
    model_config = API_CONFIG


class InternalConfig(BaseConfig):
    model_config = INTERNAL_CONFIG


class PayloadConfig(BaseConfig):
    model_config = PAYLOAD_CONFIG
