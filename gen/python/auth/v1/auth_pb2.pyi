from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AuthPayloadType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    AUTH_PAYLOAD_TYPE_UNSPECIFIED: _ClassVar[AuthPayloadType]
    AUTH_PAYLOAD_TYPE_OAUTH: _ClassVar[AuthPayloadType]
    AUTH_PAYLOAD_TYPE_SAML: _ClassVar[AuthPayloadType]
    AUTH_PAYLOAD_TYPE_BAREWORD: _ClassVar[AuthPayloadType]
    AUTH_PAYLOAD_TYPE_JWT: _ClassVar[AuthPayloadType]
    AUTH_PAYLOAD_TYPE_MTLS: _ClassVar[AuthPayloadType]
    AUTH_PAYLOAD_TYPE_API_KEY: _ClassVar[AuthPayloadType]
    AUTH_PAYLOAD_TYPE_BASIC: _ClassVar[AuthPayloadType]
    AUTH_PAYLOAD_TYPE_BEARER: _ClassVar[AuthPayloadType]
    AUTH_PAYLOAD_TYPE_CAPABILITY: _ClassVar[AuthPayloadType]
AUTH_PAYLOAD_TYPE_UNSPECIFIED: AuthPayloadType
AUTH_PAYLOAD_TYPE_OAUTH: AuthPayloadType
AUTH_PAYLOAD_TYPE_SAML: AuthPayloadType
AUTH_PAYLOAD_TYPE_BAREWORD: AuthPayloadType
AUTH_PAYLOAD_TYPE_JWT: AuthPayloadType
AUTH_PAYLOAD_TYPE_MTLS: AuthPayloadType
AUTH_PAYLOAD_TYPE_API_KEY: AuthPayloadType
AUTH_PAYLOAD_TYPE_BASIC: AuthPayloadType
AUTH_PAYLOAD_TYPE_BEARER: AuthPayloadType
AUTH_PAYLOAD_TYPE_CAPABILITY: AuthPayloadType

class AuthPayload(_message.Message):
    __slots__ = ("type", "payload")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    type: AuthPayloadType
    payload: bytes
    def __init__(self, type: _Optional[_Union[AuthPayloadType, str]] = ..., payload: _Optional[bytes] = ...) -> None: ...
