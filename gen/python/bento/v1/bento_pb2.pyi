import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class BentoState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BENTO_STATE_UNSPECIFIED: _ClassVar[BentoState]
    BENTO_STATE_NOTICED: _ClassVar[BentoState]
    BENTO_STATE_COOK: _ClassVar[BentoState]
    BENTO_STATE_PARTIAL: _ClassVar[BentoState]
    BENTO_STATE_DONE: _ClassVar[BentoState]
    BENTO_STATE_FAILED: _ClassVar[BentoState]
    BENTO_STATE_CHEW: _ClassVar[BentoState]
    BENTO_STATE_DIGEST: _ClassVar[BentoState]
    BENTO_STATE_SPOILED: _ClassVar[BentoState]

class BanchanAssetKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BANCHAN_ASSET_KIND_UNSPECIFIED: _ClassVar[BanchanAssetKind]
    BANCHAN_ASSET_KIND_PRE_FLIGHT: _ClassVar[BanchanAssetKind]
    BANCHAN_ASSET_KIND_ACCEPTANCE_TEST: _ClassVar[BanchanAssetKind]
    BANCHAN_ASSET_KIND_COMPATIBILITY_TEST: _ClassVar[BanchanAssetKind]
BENTO_STATE_UNSPECIFIED: BentoState
BENTO_STATE_NOTICED: BentoState
BENTO_STATE_COOK: BentoState
BENTO_STATE_PARTIAL: BentoState
BENTO_STATE_DONE: BentoState
BENTO_STATE_FAILED: BentoState
BENTO_STATE_CHEW: BentoState
BENTO_STATE_DIGEST: BentoState
BENTO_STATE_SPOILED: BentoState
BANCHAN_ASSET_KIND_UNSPECIFIED: BanchanAssetKind
BANCHAN_ASSET_KIND_PRE_FLIGHT: BanchanAssetKind
BANCHAN_ASSET_KIND_ACCEPTANCE_TEST: BanchanAssetKind
BANCHAN_ASSET_KIND_COMPATIBILITY_TEST: BanchanAssetKind

class BanchanAsset(_message.Message):
    __slots__ = ("kind", "location")
    KIND_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    kind: BanchanAssetKind
    location: str
    def __init__(self, kind: _Optional[_Union[BanchanAssetKind, str]] = ..., location: _Optional[str] = ...) -> None: ...

class Banchan(_message.Message):
    __slots__ = ("guid", "name", "kind", "location", "assets")
    GUID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    ASSETS_FIELD_NUMBER: _ClassVar[int]
    guid: str
    name: str
    kind: str
    location: str
    assets: _containers.RepeatedCompositeFieldContainer[BanchanAsset]
    def __init__(self, guid: _Optional[str] = ..., name: _Optional[str] = ..., kind: _Optional[str] = ..., location: _Optional[str] = ..., assets: _Optional[_Iterable[_Union[BanchanAsset, _Mapping]]] = ...) -> None: ...

class Bento(_message.Message):
    __slots__ = ("id", "name", "kind", "state", "root_path", "created_at", "schema_json", "prompt", "banchans")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ROOT_PATH_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    SCHEMA_JSON_FIELD_NUMBER: _ClassVar[int]
    PROMPT_FIELD_NUMBER: _ClassVar[int]
    BANCHANS_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    kind: str
    state: BentoState
    root_path: str
    created_at: _timestamp_pb2.Timestamp
    schema_json: str
    prompt: str
    banchans: _containers.RepeatedCompositeFieldContainer[Banchan]
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., kind: _Optional[str] = ..., state: _Optional[_Union[BentoState, str]] = ..., root_path: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., schema_json: _Optional[str] = ..., prompt: _Optional[str] = ..., banchans: _Optional[_Iterable[_Union[Banchan, _Mapping]]] = ...) -> None: ...

class BentoLifecycleEvent(_message.Message):
    __slots__ = ("event_id", "trace_id", "bento_id", "bento_kind", "state", "handler", "started_at", "finished_at", "error_message")
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    TRACE_ID_FIELD_NUMBER: _ClassVar[int]
    BENTO_ID_FIELD_NUMBER: _ClassVar[int]
    BENTO_KIND_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    HANDLER_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    event_id: str
    trace_id: str
    bento_id: str
    bento_kind: str
    state: BentoState
    handler: str
    started_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    error_message: str
    def __init__(self, event_id: _Optional[str] = ..., trace_id: _Optional[str] = ..., bento_id: _Optional[str] = ..., bento_kind: _Optional[str] = ..., state: _Optional[_Union[BentoState, str]] = ..., handler: _Optional[str] = ..., started_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., error_message: _Optional[str] = ...) -> None: ...
