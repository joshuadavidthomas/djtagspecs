from __future__ import annotations

from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class TagSpec(BaseModel):
    version: str
    engine: str = Field("django")
    requires_engine: str | None = Field(None)
    extends: list[str] = Field(default_factory=list)
    libraries: list[TagLibrary]
    extra: dict[str, Any] | None = Field(None)


class TagLibrary(BaseModel):
    module: str
    requires_engine: str | None = Field(None)
    tags: list[Tag]
    extra: dict[str, Any] | None = Field(None)


class Tag(BaseModel):
    name: str
    tagtype: TagType = Field(alias="type")
    end: EndTag | None = Field(None)
    intermediates: list[IntermediateTag] = Field(default_factory=list)
    args: list[Arg] = Field(default_factory=list)
    extra: dict[str, Any] | None = Field(None)


TagType = Literal["block", "loader", "standalone"]


class IntermediateTag(BaseModel):
    name: str
    min: int | None = Field(None, ge=0)
    max: int | None = Field(None, ge=0)
    position: Position = Field("any")
    extra: dict[str, Any] | None = Field(None)


Position = Literal["any", "last"]


class EndTag(BaseModel):
    name: str
    required: bool = Field(True)
    extra: dict[str, Any] | None = Field(None)


class Arg(BaseModel):
    name: str
    required: bool = Field(True)
    argtype: ArgType = Field("both", alias="type")
    kind: ArgKind
    extra: dict[str, Any] | None = Field(None)


ArgType = Literal["both", "positional", "keyword"]
ArgKind = Literal[
    "any", "assignment", "choice", "literal", "modifier", "syntax", "variable"
]
