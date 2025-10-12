from __future__ import annotations

from collections import Counter
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator


def _default_spec_version() -> str:
    from . import __version__

    return __version__


class TagSpec(BaseModel):
    version: str = Field(default_factory=_default_spec_version)
    engine: str = Field("django")
    requires_engine: str | None = Field(None)
    extends: list[str] = Field(default_factory=list)
    libraries: list[TagLibrary] = Field(
        default_factory=list, json_schema_extra={"default": []}
    )
    extra: dict[str, Any] | None = Field(None)

    @field_validator("libraries")
    @classmethod
    def validate_unique_modules(cls, libs: list[TagLibrary]) -> list[TagLibrary]:
        modules = [lib.module for lib in libs]
        duplicates = {module for module, count in Counter(modules).items() if count > 1}
        if duplicates:
            raise ValueError(f"Duplicate library modules found: {duplicates}")
        return libs


class TagLibrary(BaseModel):
    module: str
    requires_engine: str | None = Field(None)
    tags: list[Tag] = Field(default_factory=list, json_schema_extra={"default": []})
    extra: dict[str, Any] | None = Field(None)

    @field_validator("tags")
    @classmethod
    def validate_unique_tag_names(cls, tags: list[Tag]) -> list[Tag]:
        names = [tag.name for tag in tags]
        duplicates = {name for name, count in Counter(names).items() if count > 1}
        if duplicates:
            raise ValueError(f"Duplicate tag names found: {duplicates}")
        return tags


class Tag(BaseModel):
    name: str
    tagtype: TagType = Field(alias="type")
    end: EndTag | None = Field(None)
    intermediates: list[IntermediateTag] = Field(
        default_factory=list, json_schema_extra={"default": []}
    )
    args: list[TagArg] = Field(default_factory=list, json_schema_extra={"default": []})
    extra: dict[str, Any] | None = Field(None)

    @model_validator(mode="after")
    def validate_tag_type_constraints(self):
        if self.end and not self.end.name:
            raise ValueError(
                f"End tag for '{self.name}' MUST provide a name when declared"
            )

        if self.tagtype == "block":
            if self.end is None:
                self.end = EndTag(name=f"end{self.name}")
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
                f"Duplicate argument names found in tag args: {duplicates}"
            )
        return args

    @field_validator("intermediates")
    @classmethod
    def validate_single_last_position(
        cls, intermediates: list[IntermediateTag]
    ) -> list[IntermediateTag]:
        last_positions = [i.name for i in intermediates if i.position == "last"]
        if len(last_positions) > 1:
            raise ValueError(
                f"Multiple intermediates cannot have position='last': {last_positions}"
            )
        return intermediates


TagType = Literal["block", "loader", "standalone"]


class IntermediateTag(BaseModel):
    name: str
    args: list[TagArg] = Field(default_factory=list, json_schema_extra={"default": []})
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
                f"Duplicate argument names found in intermediate args: {duplicates}"
            )
        return args


Position = Literal["any", "last"]


class EndTag(BaseModel):
    name: str
    args: list[TagArg] = Field(default_factory=list, json_schema_extra={"default": []})
    required: bool = Field(True)
    extra: dict[str, Any] | None = Field(None)

    @field_validator("args")
    @classmethod
    def validate_unique_arg_names(cls, args: list[TagArg]) -> list[TagArg]:
        names = [arg.name for arg in args]
        duplicates = {name for name, count in Counter(names).items() if count > 1}
        if duplicates:
            raise ValueError(
                f"Duplicate argument names found in end tag args: {duplicates}"
            )
        return args


class TagArg(BaseModel):
    name: str
    required: bool = Field(True)
    argtype: TagArgType = Field("both", alias="type")
    kind: TagArgKind
    count: int | None = Field(None)
    extra: dict[str, Any] | None = Field(None)

    @field_validator("count")
    @classmethod
    def validate_count_non_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("count must be non-negative")
        return v


TagArgType = Literal["both", "positional", "keyword"]
TagArgKind = Literal[
    "any", "assignment", "choice", "literal", "modifier", "syntax", "variable"
]
