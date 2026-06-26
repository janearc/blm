from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Modality(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MODALITY_UNSPECIFIED: _ClassVar[Modality]
    MODALITY_TEXT: _ClassVar[Modality]
    MODALITY_AUDIO: _ClassVar[Modality]
    MODALITY_IMAGE: _ClassVar[Modality]

class Architecture(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ARCHITECTURE_UNSPECIFIED: _ClassVar[Architecture]
    ARCHITECTURE_DECODER: _ClassVar[Architecture]
    ARCHITECTURE_ENCODER_DECODER: _ClassVar[Architecture]
    ARCHITECTURE_ENCODER: _ClassVar[Architecture]

class Role(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ROLE_UNSPECIFIED: _ClassVar[Role]
    ROLE_CHAT: _ClassVar[Role]
    ROLE_COMPLETION: _ClassVar[Role]
    ROLE_EMBEDDING: _ClassVar[Role]
    ROLE_TRANSCRIPTION: _ClassVar[Role]
    ROLE_AUDIO_ANNOTATION: _ClassVar[Role]
    ROLE_IMAGE_GENERATION: _ClassVar[Role]
    ROLE_SPEECH_SYNTHESIS: _ClassVar[Role]

class Provider(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROVIDER_UNSPECIFIED: _ClassVar[Provider]
    PROVIDER_OLLAMA: _ClassVar[Provider]
    PROVIDER_IN_PROCESS: _ClassVar[Provider]
    PROVIDER_OPENAI_COMPATIBLE: _ClassVar[Provider]
    PROVIDER_ANTHROPIC: _ClassVar[Provider]
    PROVIDER_COMFYUI: _ClassVar[Provider]
    PROVIDER_APPLE_ON_DEVICE: _ClassVar[Provider]
MODALITY_UNSPECIFIED: Modality
MODALITY_TEXT: Modality
MODALITY_AUDIO: Modality
MODALITY_IMAGE: Modality
ARCHITECTURE_UNSPECIFIED: Architecture
ARCHITECTURE_DECODER: Architecture
ARCHITECTURE_ENCODER_DECODER: Architecture
ARCHITECTURE_ENCODER: Architecture
ROLE_UNSPECIFIED: Role
ROLE_CHAT: Role
ROLE_COMPLETION: Role
ROLE_EMBEDDING: Role
ROLE_TRANSCRIPTION: Role
ROLE_AUDIO_ANNOTATION: Role
ROLE_IMAGE_GENERATION: Role
ROLE_SPEECH_SYNTHESIS: Role
PROVIDER_UNSPECIFIED: Provider
PROVIDER_OLLAMA: Provider
PROVIDER_IN_PROCESS: Provider
PROVIDER_OPENAI_COMPATIBLE: Provider
PROVIDER_ANTHROPIC: Provider
PROVIDER_COMFYUI: Provider
PROVIDER_APPLE_ON_DEVICE: Provider

class ModelDescriptor(_message.Message):
    __slots__ = ("name", "modality", "architecture", "role", "provider", "endpoint", "model_id", "auth_secret")
    NAME_FIELD_NUMBER: _ClassVar[int]
    MODALITY_FIELD_NUMBER: _ClassVar[int]
    ARCHITECTURE_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    AUTH_SECRET_FIELD_NUMBER: _ClassVar[int]
    name: str
    modality: Modality
    architecture: Architecture
    role: Role
    provider: Provider
    endpoint: str
    model_id: str
    auth_secret: str
    def __init__(self, name: _Optional[str] = ..., modality: _Optional[_Union[Modality, str]] = ..., architecture: _Optional[_Union[Architecture, str]] = ..., role: _Optional[_Union[Role, str]] = ..., provider: _Optional[_Union[Provider, str]] = ..., endpoint: _Optional[str] = ..., model_id: _Optional[str] = ..., auth_secret: _Optional[str] = ...) -> None: ...

class ModelFamily(_message.Message):
    __slots__ = ("name", "description", "modality", "role", "members", "default_member")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    MODALITY_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    MEMBERS_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_MEMBER_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    modality: Modality
    role: Role
    members: _containers.RepeatedCompositeFieldContainer[ModelDescriptor]
    default_member: str
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., modality: _Optional[_Union[Modality, str]] = ..., role: _Optional[_Union[Role, str]] = ..., members: _Optional[_Iterable[_Union[ModelDescriptor, _Mapping]]] = ..., default_member: _Optional[str] = ...) -> None: ...

class ModelCatalog(_message.Message):
    __slots__ = ("families",)
    FAMILIES_FIELD_NUMBER: _ClassVar[int]
    families: _containers.RepeatedCompositeFieldContainer[ModelFamily]
    def __init__(self, families: _Optional[_Iterable[_Union[ModelFamily, _Mapping]]] = ...) -> None: ...
