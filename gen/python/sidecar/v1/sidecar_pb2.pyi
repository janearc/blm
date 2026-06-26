from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Capability(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CAPABILITY_UNSPECIFIED: _ClassVar[Capability]
    CAPABILITY_MODEL: _ClassVar[Capability]

class Language(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LANGUAGE_UNSPECIFIED: _ClassVar[Language]
    LANGUAGE_SWIFT: _ClassVar[Language]
    LANGUAGE_GO: _ClassVar[Language]
    LANGUAGE_PYTHON: _ClassVar[Language]
CAPABILITY_UNSPECIFIED: Capability
CAPABILITY_MODEL: Capability
LANGUAGE_UNSPECIFIED: Language
LANGUAGE_SWIFT: Language
LANGUAGE_GO: Language
LANGUAGE_PYTHON: Language

class SidecarDescriptor(_message.Message):
    __slots__ = ("name", "capability", "language", "endpoint", "health_path")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CAPABILITY_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    HEALTH_PATH_FIELD_NUMBER: _ClassVar[int]
    name: str
    capability: Capability
    language: Language
    endpoint: str
    health_path: str
    def __init__(self, name: _Optional[str] = ..., capability: _Optional[_Union[Capability, str]] = ..., language: _Optional[_Union[Language, str]] = ..., endpoint: _Optional[str] = ..., health_path: _Optional[str] = ...) -> None: ...
