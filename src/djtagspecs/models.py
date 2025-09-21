from __future__ import annotations

from collections import Counter
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator


class TagSpec(BaseModel):
    version: str
    engine: str = Field("django")
    requires_engine: str | None = Field(None)
    extends: list[str] = Field(default_factory=list)
    libraries: list[TagLibrary]
    extra: dict[str, Any] | None = Field(None)

    @field_validator("libraries")
    @classmethod
    def validate_unique_modules(cls, libs: list[TagLibrary]) -> list[TagLibrary]:
        modules = [lib.module for lib in libs]
        duplicates = {module for module, count in Counter(modules).items() if count > 1}
        if duplicates:
            raise ValueError(f"Duplicate library modules found: {set(duplicates)}")
        return libs


class TagLibrary(BaseModel):
    module: str
    requires_engine: str | None = Field(None)
    tags: list[Tag]
    extra: dict[str, Any] | None = Field(None)

    @field_validator("tags")
    @classmethod
    def validate_unique_tag_names(cls, tags: list[Tag]) -> list[Tag]:
        names = [tag.name for tag in tags]
        duplicates = {name for name, count in Counter(names).items() if count > 1}
        if duplicates:
            raise ValueError(f"Duplicate tag names found: {set(duplicates)}")
        return tags


class Tag(BaseModel):
    name: str
    tagtype: TagType = Field(alias="type")
    end: EndTag | None = Field(None)
    intermediates: list[IntermediateTag] = Field(default_factory=list)
    args: list[TagArg] = Field(default_factory=list)
    extra: dict[str, Any] | None = Field(None)

    @model_validator(mode="after")
    def validate_tag_type_constraints(self):
        if self.tagtype == "block":
            if not self.end:
                raise ValueError(f"Block tag '{self.name}' MUST define an end tag")
        elif self.tagtype == "standalone":
            if self.end:
                raise ValueError(
                    f"Standalone tag '{self.name}' MUST NOT have an end tag"
                )
            if self.intermediates:
                raise ValueError(
                    f"Standalone tag '{self.name}' MUST NOT have intermediate tags"
                )
        return self

    @field_validator("args")
    @classmethod
    def validate_unique_arg_names(cls, args: list[TagArg]) -> list[TagArg]:
        names = [arg.name for arg in args]
        duplicates = {name for name, count in Counter(names).items() if count > 1}
        if duplicates:
            raise ValueError(
                f"Duplicate argument names found in tag args: {set(duplicates)}"
            )
        return args


TagType = Literal["block", "loader", "standalone"]


class IntermediateTag(BaseModel):
    name: str
    args: list[TagArg] = Field(default_factory=list)
    min: int | None = Field(None, ge=0)
    max: int | None = Field(None, ge=0)
    position: Position = Field("any")
    extra: dict[str, Any] | None = Field(None)

    @model_validator(mode="after")
    def validate_min_max_relationship(self):
        if self.min is not None and self.max is not None:
            if self.max < self.min:
                raise ValueError(
                    f"Intermediate tag '{self.name}': max ({self.max}) must be >= min ({self.min})"
                )
        return self

    @field_validator("args")
    @classmethod
    def validate_unique_arg_names(cls, args: list[TagArg]) -> list[TagArg]:
        names = [arg.name for arg in args]
        duplicates = {name for name, count in Counter(names).items() if count > 1}
        if duplicates:
            raise ValueError(
                f"Duplicate argument names found in intermediate args: {set(duplicates)}"
            )
        return args


Position = Literal["any", "last"]


class EndTag(BaseModel):
    name: str
    args: list[TagArg] = Field(default_factory=list)
    required: bool = Field(True)
    extra: dict[str, Any] | None = Field(None)

    @field_validator("args")
    @classmethod
    def validate_unique_arg_names(cls, args: list[TagArg]) -> list[TagArg]:
        names = [arg.name for arg in args]
        duplicates = {name for name, count in Counter(names).items() if count > 1}
        if duplicates:
            raise ValueError(
                f"Duplicate argument names found in end tag args: {set(duplicates)}"
            )
        return args


class TagArg(BaseModel):
    name: str
    required: bool = Field(True)
    argtype: TagArgType = Field("both", alias="type")
    kind: TagArgKind
    extra: dict[str, Any] | None = Field(None)


TagArgType = Literal["both", "positional", "keyword"]
TagArgKind = Literal[
    "any", "assignment", "choice", "literal", "modifier", "syntax", "variable"
]
