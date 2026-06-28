import datetime

from auth.v1 import auth_pb2 as _auth_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Cell(_message.Message):
    __slots__ = ("row_key", "column", "ref_key", "body", "created_at")
    ROW_KEY_FIELD_NUMBER: _ClassVar[int]
    COLUMN_FIELD_NUMBER: _ClassVar[int]
    REF_KEY_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    row_key: str
    column: str
    ref_key: int
    body: _struct_pb2.Struct
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, row_key: _Optional[str] = ..., column: _Optional[str] = ..., ref_key: _Optional[int] = ..., body: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetRequest(_message.Message):
    __slots__ = ("namespace", "row_key", "column", "ref_key", "credentials")
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    ROW_KEY_FIELD_NUMBER: _ClassVar[int]
    COLUMN_FIELD_NUMBER: _ClassVar[int]
    REF_KEY_FIELD_NUMBER: _ClassVar[int]
    CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
    namespace: str
    row_key: str
    column: str
    ref_key: int
    credentials: _containers.RepeatedCompositeFieldContainer[_auth_pb2.AuthPayload]
    def __init__(self, namespace: _Optional[str] = ..., row_key: _Optional[str] = ..., column: _Optional[str] = ..., ref_key: _Optional[int] = ..., credentials: _Optional[_Iterable[_Union[_auth_pb2.AuthPayload, _Mapping]]] = ...) -> None: ...

class GetResponse(_message.Message):
    __slots__ = ("cell", "found")
    CELL_FIELD_NUMBER: _ClassVar[int]
    FOUND_FIELD_NUMBER: _ClassVar[int]
    cell: Cell
    found: bool
    def __init__(self, cell: _Optional[_Union[Cell, _Mapping]] = ..., found: _Optional[bool] = ...) -> None: ...

class GetLatestRequest(_message.Message):
    __slots__ = ("namespace", "row_key", "column", "credentials")
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    ROW_KEY_FIELD_NUMBER: _ClassVar[int]
    COLUMN_FIELD_NUMBER: _ClassVar[int]
    CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
    namespace: str
    row_key: str
    column: str
    credentials: _containers.RepeatedCompositeFieldContainer[_auth_pb2.AuthPayload]
    def __init__(self, namespace: _Optional[str] = ..., row_key: _Optional[str] = ..., column: _Optional[str] = ..., credentials: _Optional[_Iterable[_Union[_auth_pb2.AuthPayload, _Mapping]]] = ...) -> None: ...

class GetLatestResponse(_message.Message):
    __slots__ = ("cell", "found")
    CELL_FIELD_NUMBER: _ClassVar[int]
    FOUND_FIELD_NUMBER: _ClassVar[int]
    cell: Cell
    found: bool
    def __init__(self, cell: _Optional[_Union[Cell, _Mapping]] = ..., found: _Optional[bool] = ...) -> None: ...

class PutRequest(_message.Message):
    __slots__ = ("namespace", "row_key", "column", "ref_key", "body", "credentials")
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    ROW_KEY_FIELD_NUMBER: _ClassVar[int]
    COLUMN_FIELD_NUMBER: _ClassVar[int]
    REF_KEY_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
    namespace: str
    row_key: str
    column: str
    ref_key: int
    body: _struct_pb2.Struct
    credentials: _containers.RepeatedCompositeFieldContainer[_auth_pb2.AuthPayload]
    def __init__(self, namespace: _Optional[str] = ..., row_key: _Optional[str] = ..., column: _Optional[str] = ..., ref_key: _Optional[int] = ..., body: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., credentials: _Optional[_Iterable[_Union[_auth_pb2.AuthPayload, _Mapping]]] = ...) -> None: ...

class PutResponse(_message.Message):
    __slots__ = ("row_key", "column", "ref_key")
    ROW_KEY_FIELD_NUMBER: _ClassVar[int]
    COLUMN_FIELD_NUMBER: _ClassVar[int]
    REF_KEY_FIELD_NUMBER: _ClassVar[int]
    row_key: str
    column: str
    ref_key: int
    def __init__(self, row_key: _Optional[str] = ..., column: _Optional[str] = ..., ref_key: _Optional[int] = ...) -> None: ...

class QueryRequest(_message.Message):
    __slots__ = ("namespace", "index", "predicates", "shard_hint", "limit", "credentials")
    class PredicatesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: _struct_pb2.Value
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[_struct_pb2.Value, _Mapping]] = ...) -> None: ...
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    PREDICATES_FIELD_NUMBER: _ClassVar[int]
    SHARD_HINT_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
    namespace: str
    index: str
    predicates: _containers.MessageMap[str, _struct_pb2.Value]
    shard_hint: str
    limit: int
    credentials: _containers.RepeatedCompositeFieldContainer[_auth_pb2.AuthPayload]
    def __init__(self, namespace: _Optional[str] = ..., index: _Optional[str] = ..., predicates: _Optional[_Mapping[str, _struct_pb2.Value]] = ..., shard_hint: _Optional[str] = ..., limit: _Optional[int] = ..., credentials: _Optional[_Iterable[_Union[_auth_pb2.AuthPayload, _Mapping]]] = ...) -> None: ...

class QueryResponse(_message.Message):
    __slots__ = ("rows", "next_page_token")
    ROWS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    rows: _containers.RepeatedCompositeFieldContainer[Cell]
    next_page_token: str
    def __init__(self, rows: _Optional[_Iterable[_Union[Cell, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
