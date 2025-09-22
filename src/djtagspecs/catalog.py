from __future__ import annotations

import json
from collections.abc import Mapping
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Any

import tomli
import tomli_w

from djtagspecs.models import TagLibrary
from djtagspecs.models import TagSpec


class TagSpecError(RuntimeError):
    """Base error for TagSpec operations."""


class TagSpecLoadError(TagSpecError):
    """Raised when a TagSpec document cannot be loaded."""


class TagSpecResolutionError(TagSpecError):
    """Raised when resolving document composition fails."""


class TagSpecFormat(str, Enum):
    JSON = "json"
    TOML = "toml"

    @classmethod
    def from_path(cls, path: Path) -> TagSpecFormat:
        suffix = path.suffix.lower()
        for member in cls:
            if suffix == member.extension:
                return member
        raise TagSpecLoadError(
            f"Cannot infer format from extension '{suffix}' for document {path}"
        )

    @classmethod
    def coerce(cls, value: TagSpecFormat | str) -> TagSpecFormat:
        if isinstance(value, cls):
            return value
        try:
            return cls(value.lower())
        except ValueError as exc:
            choices = ", ".join(member.value for member in cls)
            raise TagSpecError(
                f"Unsupported TagSpec format '{value}'. Choose one of: {choices}."
            ) from exc

    @property
    def extension(self) -> str:
        return f".{self.value}"

    def load(self, path: Path) -> Mapping[str, Any]:
        try:
            match self:
                case TagSpecFormat.JSON:
                    return json.loads(path.read_text(encoding="utf-8"))
                case TagSpecFormat.TOML:
                    with path.open("rb") as fh:
                        return tomli.load(fh)
        except (tomli.TOMLDecodeError, json.JSONDecodeError) as exc:
            raise TagSpecLoadError(
                f"Failed to parse TagSpec document {path}: {exc}"
            ) from exc

    def dump(self, payload: Mapping[str, Any]) -> str:
        match self:
            case TagSpecFormat.JSON:
                return json.dumps(payload, indent=2, sort_keys=True)
            case TagSpecFormat.TOML:
                return tomli_w.dumps(payload)


class TagSpecLoader:
    """Load TagSpec documents from disk and resolve their overlays."""

    def __init__(self) -> None:
        self._cache: dict[Path, TagSpec] = {}

    def load(self, path: str | Path, *, resolve_extends: bool = True) -> TagSpec:
        path = Path(path)
        if resolve_extends:
            return self._resolve_path(path)
        return self._load_raw(path)

    def _load_raw(self, path: Path) -> TagSpec:
        resolved = path.resolve()
        if resolved in self._cache:
            return self._cache[resolved]
        fmt = TagSpecFormat.from_path(resolved)
        try:
            payload = fmt.load(resolved)
        except FileNotFoundError as exc:
            raise TagSpecLoadError(f"TagSpec document not found: {resolved}") from exc

        try:
            spec = TagSpec.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            raise TagSpecLoadError(
                f"Document {resolved} is not a valid TagSpec: {exc}"
            ) from exc

        self._cache[resolved] = spec
        return spec

    def _resolve_path(self, path: Path) -> TagSpec:
        resolved_path = path.resolve()
        seen: list[Path] = []

        def _inner(current_path: Path) -> TagSpec:
            current_resolved = current_path.resolve()
            if current_resolved in seen:
                cycle = " -> ".join(str(p) for p in seen + [current_resolved])
                raise TagSpecResolutionError(
                    f"Circular extends chain detected: {cycle}"
                )
            seen.append(current_resolved)
            spec = self._load_raw(current_path)
            base: TagSpec | None = None
            for reference in spec.extends:
                ref_path = Path(reference)
                if not ref_path.is_absolute():
                    ref_path = current_resolved.parent / ref_path
                child = _inner(ref_path)
                base = child if base is None else merge_tag_specs(base, child)
            seen.pop()
            if base is None:
                return spec
            merged = merge_tag_specs(base, spec)
            return merged.model_copy(update={"extends": []})

        resolved_spec = _inner(resolved_path)
        validate_tag_spec(resolved_spec)
        return resolved_spec


def load_tag_spec(path: str | Path, *, resolve_extends: bool = True) -> TagSpec:
    """Load a TagSpec document from disk."""

    loader = TagSpecLoader()
    spec = loader.load(path, resolve_extends=resolve_extends)
    if not resolve_extends:
        validate_tag_spec(spec)
    return spec


def merge_tag_specs(base: TagSpec, overlay: TagSpec) -> TagSpec:
    """Merge two TagSpec documents, applying `overlay` on top of `base`."""

    engine = overlay.engine if "engine" in overlay.model_fields_set else base.engine
    requires_engine = (
        overlay.requires_engine
        if "requires_engine" in overlay.model_fields_set
        else base.requires_engine
    )
    version = overlay.version if "version" in overlay.model_fields_set else base.version
    extra = _merge_optional_mapping(base.extra, overlay.extra, overlay, "extra")
    libraries = _merge_libraries(base.libraries, overlay.libraries)

    return TagSpec(
        version=version,
        engine=engine,
        requires_engine=requires_engine,
        extends=overlay.extends if overlay.extends else [],
        libraries=libraries,
        extra=extra,
    )


def dump_tag_spec(
    spec: TagSpec, *, format: TagSpecFormat | str = TagSpecFormat.TOML
) -> str:
    """Serialise a TagSpec to the requested format."""

    payload = spec.model_dump(by_alias=True, exclude_none=True)
    fmt = TagSpecFormat.coerce(format)
    return fmt.dump(payload)


def validate_tag_spec(spec: TagSpec) -> None:
    """Perform structural validation that complements model validators."""

    module_seen: set[str] = set()
    for library in spec.libraries:
        if library.module in module_seen:
            raise TagSpecResolutionError(
                f"Duplicate library module detected after merge: {library.module}"
            )
        module_seen.add(library.module)

        tag_seen: set[str] = set()
        for tag in library.tags:
            if tag.name in tag_seen:
                raise TagSpecResolutionError(
                    f"Duplicate tag detected in library {library.module}: {tag.name}"
                )
            tag_seen.add(tag.name)


def _merge_libraries(
    base: Sequence[TagLibrary], overlay: Sequence[TagLibrary]
) -> list[TagLibrary]:
    module_index = {lib.module: idx for idx, lib in enumerate(base)}
    result = list(base)
    pending: list[TagLibrary] = []

    for lib in overlay:
        if lib.module in module_index:
            idx = module_index[lib.module]
            result[idx] = _merge_library(result[idx], lib)
        else:
            pending.append(lib)

    result.extend(pending)
    return result


def _merge_library(base: TagLibrary, overlay: TagLibrary) -> TagLibrary:
    if overlay.module != base.module:
        raise TagSpecResolutionError(
            "Cannot merge libraries with different modules: "
            f"{base.module} vs {overlay.module}"
        )

    requires_engine = (
        overlay.requires_engine
        if "requires_engine" in overlay.model_fields_set
        else base.requires_engine
    )
    extra = _merge_optional_mapping(base.extra, overlay.extra, overlay, "extra")

    base_tags = {tag.name: tag for tag in base.tags}
    order = list(base.tags)

    appended = []
    for tag in overlay.tags:
        if tag.name in base_tags:
            idx = order.index(base_tags[tag.name])
            order[idx] = tag
        else:
            appended.append(tag)

    order.extend(appended)

    return TagLibrary(
        module=overlay.module,
        requires_engine=requires_engine,
        tags=order,
        extra=extra,
    )


def _merge_optional_mapping(
    base: Mapping[str, Any] | None,
    overlay: Mapping[str, Any] | None,
    model: Any,
    field_name: str,
) -> Mapping[str, Any] | None:
    if field_name not in getattr(model, "model_fields_set", set()):
        return base
    if overlay is None:
        return None
    merged: dict[str, Any] = {}
    if base:
        merged.update(base)
    merged.update(overlay)
    return merged
