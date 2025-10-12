from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from djtagspecs import Tag
from djtagspecs import TagArg
from djtagspecs import TagLibrary
from djtagspecs import TagSpec
from djtagspecs import __version__
from djtagspecs.catalog import TagSpecResolutionError
from djtagspecs.catalog import load_tag_spec
from djtagspecs.catalog import merge_tag_specs
from djtagspecs.catalog import validate_tag_spec


def test_load_simple_document(tmp_path: Path) -> None:
    path = tmp_path / "base.toml"
    path.write_text(
        """
        [[libraries]]
        module = "example"

        [[libraries.tags]]
        name = "hello"
        type = "standalone"
        """.strip(),
    )

    spec = load_tag_spec(path, resolve_extends=False)

    assert spec.version == __version__
    assert spec.extends == []
    assert spec.libraries[0].module == "example"
    assert spec.libraries[0].tags[0].name == "hello"


def test_resolve_extends_merges_tags(tmp_path: Path) -> None:
    base = tmp_path / "base.toml"
    base.write_text(
        """
        [[libraries]]
        module = "example"

        [[libraries.tags]]
        name = "hello"
        type = "standalone"

        [[libraries.tags]]
        name = "base_only"
        type = "standalone"
        """.strip(),
    )

    overlay = tmp_path / "overlay.toml"
    overlay.write_text(
        """
        extends = ["base.toml"]

        [[libraries]]
        module = "example"

        [[libraries.tags]]
        name = "hello"
        type = "standalone"
        [libraries.tags.extra]
        source = "overlay"

        [[libraries.tags]]
        name = "overlay_only"
        type = "standalone"
        """.strip(),
    )

    spec = load_tag_spec(overlay)

    library = spec.libraries[0]
    tag_names = [tag.name for tag in library.tags]
    extra_lookup = {tag.name: tag.extra for tag in library.tags}

    assert tag_names == ["hello", "base_only", "overlay_only"]
    assert extra_lookup["hello"] == {"source": "overlay"}


def test_validate_detects_duplicate_modules() -> None:
    spec = TagSpec.model_construct(
        version=__version__,
        libraries=[
            TagLibrary.model_construct(
                module="dup",
                tags=[Tag.model_construct(name="a", tagtype="standalone")],
            ),
            TagLibrary.model_construct(
                module="dup",
                tags=[Tag.model_construct(name="b", tagtype="standalone")],
            ),
        ],
    )

    with pytest.raises(TagSpecResolutionError):
        validate_tag_spec(spec)


def test_merge_appends_new_library():
    base = TagSpec.model_construct(
        version=__version__,
        libraries=[
            TagLibrary.model_construct(
                module="example",
                tags=[Tag.model_construct(name="hello", type="standalone")],
            )
        ],
    )
    overlay = TagSpec.model_construct(
        version=__version__,
        libraries=[
            TagLibrary.model_construct(
                module="other",
                tags=[Tag.model_construct(name="bye", type="standalone")],
            )
        ],
    )

    merged = merge_tag_specs(base, overlay)

    assert [lib.module for lib in merged.libraries] == ["example", "other"]


def test_tag_spec_defaults_version() -> None:
    spec = TagSpec(
        libraries=[TagLibrary(module="example", tags=[])],
    )

    assert spec.version == __version__


def test_resolve_package_reference(tmp_path: Path, monkeypatch) -> None:
    package_root = tmp_path / "pkgexample"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "catalog.toml").write_text(
        """
        [[libraries]]
        module = "pkg.example"

        [[libraries.tags]]
        name = "pkg_tag"
        type = "standalone"
        """.strip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    document = tmp_path / "local.toml"
    document.write_text(
        """
        extends = ["pkg://pkgexample/catalog.toml"]

        [[libraries]]
        module = "local.example"

        [[libraries.tags]]
        name = "local_tag"
        type = "standalone"
        """.strip(),
        encoding="utf-8",
    )

    try:
        spec = load_tag_spec(document)
    finally:
        sys.modules.pop("pkgexample", None)

    modules = [lib.module for lib in spec.libraries]
    assert modules == ["pkg.example", "local.example"]

    pkg_tag = next(tag for tag in spec.libraries[0].tags if tag.name == "pkg_tag")
    local_tag = next(tag for tag in spec.libraries[1].tags if tag.name == "local_tag")

    assert pkg_tag.tagtype == "standalone"
    assert local_tag.tagtype == "standalone"


def test_block_tag_defaults_end_tag() -> None:
    tag = Tag.model_validate({"name": "hero", "type": "block"})

    assert tag.end is not None
    assert tag.end.name == "endhero"
    assert tag.end.args == []
    assert tag.end.required is True


def test_explicit_end_requires_name() -> None:
    with pytest.raises(ValueError) as excinfo:
        Tag.model_validate({"name": "hero", "type": "block", "end": {"name": ""}})

    assert "MUST provide a name" in str(excinfo.value)


def test_tag_arg_count_none_default() -> None:
    arg = TagArg(name="test", kind="variable")
    assert arg.count is None


def test_tag_arg_count_integer() -> None:
    arg = TagArg(name="test", kind="variable", count=1)
    assert arg.count == 1

    arg = TagArg(name="test", kind="variable", count=3)
    assert arg.count == 3


def test_tag_arg_count_zero_valid() -> None:
    arg = TagArg(name="test", kind="variable", count=0)
    assert arg.count == 0


def test_tag_arg_count_negative_invalid() -> None:
    with pytest.raises(ValueError, match="count must be non-negative"):
        TagArg(name="test", kind="variable", count=-1)


def test_tag_arg_count_serialization() -> None:
    tag = Tag(
        name="test",
        type="standalone",
        args=[
            TagArg(name="arg1", kind="variable", count=1),
            TagArg(name="arg2", kind="variable"),
        ],
    )

    data = tag.model_dump(by_alias=True, exclude_none=True)
    assert data["args"][0]["count"] == 1
    assert "count" not in data["args"][1]


def test_tag_arg_count_in_full_spec() -> None:
    spec = TagSpec(
        version="0.5.0",
        engine="django",
        libraries=[
            TagLibrary(
                module="test.tags",
                tags=[
                    Tag(
                        name="widthratio",
                        type="standalone",
                        args=[
                            TagArg(name="value", kind="variable", count=1),
                            TagArg(name="max_value", kind="variable", count=1),
                            TagArg(name="max_width", kind="variable", count=1),
                        ],
                    )
                ],
            )
        ],
    )

    assert spec.libraries[0].tags[0].args[0].count == 1
    assert spec.libraries[0].tags[0].args[1].count == 1
    assert spec.libraries[0].tags[0].args[2].count == 1
