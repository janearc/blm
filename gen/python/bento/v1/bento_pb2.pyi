import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class BentoState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BENTO_STATE_UNSPECIFIED: _ClassVar[BentoState]
    BENTO_STATE_IDLE: _ClassVar[BentoState]
    BENTO_STATE_PROCESSING: _ClassVar[BentoState]
    BENTO_STATE_DONE: _ClassVar[BentoState]
    BENTO_STATE_FAILED: _ClassVar[BentoState]

class BanchanState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BANCHAN_STATE_UNSPECIFIED: _ClassVar[BanchanState]
    BANCHAN_STATE_NOT_STARTED: _ClassVar[BanchanState]
    BANCHAN_STATE_IN_PROGRESS: _ClassVar[BanchanState]
    BANCHAN_STATE_PARTIAL: _ClassVar[BanchanState]
    BANCHAN_STATE_NEEDS_MASSAGE: _ClassVar[BanchanState]
    BANCHAN_STATE_DONE: _ClassVar[BanchanState]
    BANCHAN_STATE_FAILED: _ClassVar[BanchanState]
BENTO_STATE_UNSPECIFIED: BentoState
BENTO_STATE_IDLE: BentoState
BENTO_STATE_PROCESSING: BentoState
BENTO_STATE_DONE: BentoState
BENTO_STATE_FAILED: BentoState
BANCHAN_STATE_UNSPECIFIED: BanchanState
BANCHAN_STATE_NOT_STARTED: BanchanState
BANCHAN_STATE_IN_PROGRESS: BanchanState
BANCHAN_STATE_PARTIAL: BanchanState
BANCHAN_STATE_NEEDS_MASSAGE: BanchanState
BANCHAN_STATE_DONE: BanchanState
BANCHAN_STATE_FAILED: BanchanState

class Bento(_message.Message):
    __slots__ = ("id", "name", "kind", "state", "root_path", "created_at", "schema_json", "prompt")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ROOT_PATH_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    SCHEMA_JSON_FIELD_NUMBER: _ClassVar[int]
    PROMPT_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    kind: str
    state: BentoState
    root_path: str
    created_at: _timestamp_pb2.Timestamp
    schema_json: str
    prompt: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., kind: _Optional[str] = ..., state: _Optional[_Union[BentoState, str]] = ..., root_path: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., schema_json: _Optional[str] = ..., prompt: _Optional[str] = ...) -> None: ...

class Banchan(_message.Message):
    __slots__ = ("id", "name", "bento_id", "state", "trace_id", "started_at", "finished_at", "error_message")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    BENTO_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    TRACE_ID_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    bento_id: str
    state: BanchanState
    trace_id: str
    started_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    error_message: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., bento_id: _Optional[str] = ..., state: _Optional[_Union[BanchanState, str]] = ..., trace_id: _Optional[str] = ..., started_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., error_message: _Optional[str] = ...) -> None: ...
