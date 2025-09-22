from __future__ import annotations

import importlib.resources
import json
from collections.abc import Mapping
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import ParseResult
from urllib.parse import urlparse

try:
    import tomllib as toml
except ModuleNotFoundError:  # pragma: no cover
    import tomli as toml  # type: ignore[no-redef]
import tomli_w

from djtagspecs.models import Tag
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
                        return toml.load(fh)
        except (toml.TOMLDecodeError, json.JSONDecodeError) as exc:
            raise TagSpecLoadError(
                f"Failed to parse TagSpec document {path}: {exc}"
            ) from exc

    def dump(self, payload: Mapping[str, Any]) -> str:
        match self:
            case TagSpecFormat.JSON:
                return json.dumps(payload, indent=2, sort_keys=True)
            case TagSpecFormat.TOML:
                return tomli_w.dumps(payload)


def load_tag_spec(path: str | Path, *, resolve_extends: bool = True) -> TagSpec:
    path = Path(path)
    cache: dict[str, TagSpec] = {}
    cache_key = str(path.resolve())
    spec = (
        _resolve_document(path, cache, stack=[], cache_key=cache_key)
        if resolve_extends
        else _load_raw(path, cache, cache_key)
    )
    validate_tag_spec(spec)
    return spec


def _load_raw(path: Path, cache: dict[str, TagSpec], cache_key: str) -> TagSpec:
    if cache_key in cache:
        return cache[cache_key]

    fmt = TagSpecFormat.from_path(path)
    try:
        payload = fmt.load(path)
    except FileNotFoundError as exc:
        raise TagSpecLoadError(f"TagSpec document not found: {path}") from exc

    try:
        spec = TagSpec.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        raise TagSpecLoadError(
            f"Document {path} is not a valid TagSpec: {exc}"
        ) from exc

    cache[cache_key] = spec
    return spec


def _resolve_document(
    path: Path,
    cache: dict[str, TagSpec],
    *,
    stack: list[str],
    cache_key: str | None = None,
) -> TagSpec:
    resolved = path.resolve()
    key = cache_key or str(resolved)

    if key in stack:
        cycle = " -> ".join(stack + [key])
        raise TagSpecResolutionError(f"Circular extends chain detected: {cycle}")

    stack.append(key)
    spec = _load_raw(resolved, cache, key)
    base: TagSpec | None = None
    for reference in spec.extends:
        child = _resolve_reference(
            reference,
            resolved,
            cache,
            stack=stack,
        )
        base = child if base is None else merge_tag_specs(base, child)
    stack.pop()

    if base is None:
        return spec

    merged = merge_tag_specs(base, spec)
    return merged.model_copy(update={"extends": []})


def _resolve_reference(
    reference: str,
    current: Path,
    cache: dict[str, TagSpec],
    *,
    stack: list[str],
) -> TagSpec:
    parsed = urlparse(reference)
    if parsed.scheme == "pkg":
        return _resolve_package_reference(reference, parsed, cache, stack=stack)

    ref_path = Path(reference)
    if not ref_path.is_absolute():
        ref_path = current.parent / ref_path
    ref_key = str(ref_path.resolve())
    return _resolve_document(ref_path, cache, stack=stack, cache_key=ref_key)


def _resolve_package_reference(
    reference: str,
    parsed: ParseResult,
    cache: dict[str, TagSpec],
    *,
    stack: list[str],
) -> TagSpec:
    package = parsed.netloc or ""
    resource_path = parsed.path.lstrip("/")

    if not package:
        raise TagSpecResolutionError(
            f"Invalid package reference '{reference}': missing module name"
        )
    if not resource_path:
        raise TagSpecResolutionError(
            f"Invalid package reference '{reference}': missing resource path"
        )

    try:
        root = importlib.resources.files(package)
    except ModuleNotFoundError as exc:
        raise TagSpecResolutionError(
            f"Unable to resolve package reference '{reference}': package '{package}' not found"
        ) from exc

    resource = root.joinpath(resource_path)
    if not resource.is_file():
        raise TagSpecResolutionError(
            f"Unable to resolve package reference '{reference}': resource '{resource_path}' not found"
        )

    cache_key = f"pkg://{package}/{resource_path}"
    with importlib.resources.as_file(resource) as tmp_path:
        return _resolve_document(
            Path(tmp_path),
            cache,
            stack=stack,
            cache_key=cache_key,
        )


def merge_tag_specs(base: TagSpec, overlay: TagSpec) -> TagSpec:
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
    payload = spec.model_dump(by_alias=True, exclude_none=True)
    fmt = TagSpecFormat.coerce(format)
    return fmt.dump(payload)


def validate_tag_spec(spec: TagSpec) -> None:
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
            f"Cannot merge libraries with different modules: {base.module} vs {overlay.module}"
        )

    requires_engine = (
        overlay.requires_engine
        if "requires_engine" in overlay.model_fields_set
        else base.requires_engine
    )
    extra = _merge_optional_mapping(base.extra, overlay.extra, overlay, "extra")

    base_tags = {tag.name: tag for tag in base.tags}
    order = list(base.tags)

    appended: list[Tag] = []
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
) -> dict[str, Any] | None:
    if field_name not in getattr(model, "model_fields_set", set()):
        return None if base is None else dict(base)
    if overlay is None:
        return None
    merged: dict[str, Any] = {}
    if base:
        merged.update(base)
    merged.update(overlay)
    return merged
