from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Identity(_message.Message):
    __slots__ = ("service_name", "project", "version")
    SERVICE_NAME_FIELD_NUMBER: _ClassVar[int]
    PROJECT_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    service_name: str
    project: str
    version: str
    def __init__(self, service_name: _Optional[str] = ..., project: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class ContractRef(_message.Message):
    __slots__ = ("subject", "version")
    SUBJECT_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    subject: str
    version: str
    def __init__(self, subject: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class ContractDescriptor(_message.Message):
    __slots__ = ("emits", "consumes", "serves")
    EMITS_FIELD_NUMBER: _ClassVar[int]
    CONSUMES_FIELD_NUMBER: _ClassVar[int]
    SERVES_FIELD_NUMBER: _ClassVar[int]
    emits: _containers.RepeatedCompositeFieldContainer[ContractRef]
    consumes: _containers.RepeatedCompositeFieldContainer[ContractRef]
    serves: _containers.RepeatedCompositeFieldContainer[ContractRef]
    def __init__(self, emits: _Optional[_Iterable[_Union[ContractRef, _Mapping]]] = ..., consumes: _Optional[_Iterable[_Union[ContractRef, _Mapping]]] = ..., serves: _Optional[_Iterable[_Union[ContractRef, _Mapping]]] = ...) -> None: ...
