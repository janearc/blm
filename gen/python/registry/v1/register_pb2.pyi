import datetime

from frood.v1 import frood_pb2 as _frood_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Endpoint(_message.Message):
    __slots__ = ("scheme", "address")
    SCHEME_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    scheme: str
    address: str
    def __init__(self, scheme: _Optional[str] = ..., address: _Optional[str] = ...) -> None: ...

class RegisterRequest(_message.Message):
    __slots__ = ("project", "identity", "contracts", "endpoints")
    PROJECT_FIELD_NUMBER: _ClassVar[int]
    IDENTITY_FIELD_NUMBER: _ClassVar[int]
    CONTRACTS_FIELD_NUMBER: _ClassVar[int]
    ENDPOINTS_FIELD_NUMBER: _ClassVar[int]
    project: str
    identity: _frood_pb2.Identity
    contracts: _frood_pb2.ContractDescriptor
    endpoints: _containers.RepeatedCompositeFieldContainer[Endpoint]
    def __init__(self, project: _Optional[str] = ..., identity: _Optional[_Union[_frood_pb2.Identity, _Mapping]] = ..., contracts: _Optional[_Union[_frood_pb2.ContractDescriptor, _Mapping]] = ..., endpoints: _Optional[_Iterable[_Union[Endpoint, _Mapping]]] = ...) -> None: ...

class RegisterResponse(_message.Message):
    __slots__ = ("identity", "endpoint", "lease_ttl_seconds", "config")
    IDENTITY_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    LEASE_TTL_SECONDS_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    identity: _frood_pb2.Identity
    endpoint: Endpoint
    lease_ttl_seconds: int
    config: _struct_pb2.Struct
    def __init__(self, identity: _Optional[_Union[_frood_pb2.Identity, _Mapping]] = ..., endpoint: _Optional[_Union[Endpoint, _Mapping]] = ..., lease_ttl_seconds: _Optional[int] = ..., config: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class Registration(_message.Message):
    __slots__ = ("project", "identity", "contracts", "endpoint", "registered_at", "lease_expires_at")
    PROJECT_FIELD_NUMBER: _ClassVar[int]
    IDENTITY_FIELD_NUMBER: _ClassVar[int]
    CONTRACTS_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    REGISTERED_AT_FIELD_NUMBER: _ClassVar[int]
    LEASE_EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    project: str
    identity: _frood_pb2.Identity
    contracts: _frood_pb2.ContractDescriptor
    endpoint: Endpoint
    registered_at: _timestamp_pb2.Timestamp
    lease_expires_at: _timestamp_pb2.Timestamp
    def __init__(self, project: _Optional[str] = ..., identity: _Optional[_Union[_frood_pb2.Identity, _Mapping]] = ..., contracts: _Optional[_Union[_frood_pb2.ContractDescriptor, _Mapping]] = ..., endpoint: _Optional[_Union[Endpoint, _Mapping]] = ..., registered_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lease_expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class RegistrationSet(_message.Message):
    __slots__ = ("registrations",)
    REGISTRATIONS_FIELD_NUMBER: _ClassVar[int]
    registrations: _containers.RepeatedCompositeFieldContainer[Registration]
    def __init__(self, registrations: _Optional[_Iterable[_Union[Registration, _Mapping]]] = ...) -> None: ...
