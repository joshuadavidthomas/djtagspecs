from __future__ import annotations

from pathlib import Path

import pytest

from djtagspecs import Tag
from djtagspecs import TagLibrary
from djtagspecs import TagSpec
from djtagspecs.catalog import TagSpecResolutionError
from djtagspecs.catalog import load_tag_spec
from djtagspecs.catalog import merge_tag_specs
from djtagspecs.catalog import validate_tag_spec


def test_load_simple_document(tmp_path: Path) -> None:
    base = tmp_path / "base.toml"
    base.write_text(
        """
        version = "0.1.0"

        [[libraries]]
        module = "example"

        [[libraries.tags]]
        name = "hello"
        type = "standalone"
        """.strip(),
    )

    spec = load_tag_spec(base, resolve_extends=False)

    assert spec.version == "0.1.0"
    assert spec.extends == []
    assert spec.libraries[0].module == "example"
    assert spec.libraries[0].tags[0].name == "hello"


def test_resolve_extends_merges_tags(tmp_path: Path) -> None:
    base = tmp_path / "base.toml"
    base.write_text(
        """
        version = "0.1.0"

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
        version = "0.1.0"
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
        version="0.1.0",
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
        version="0.1.0",
        libraries=[
            TagLibrary.model_construct(
                module="example",
                tags=[Tag.model_construct(name="hello", type="standalone")],
            )
        ],
    )
    overlay = TagSpec.model_construct(
        version="0.1.0",
        libraries=[
            TagLibrary.model_construct(
                module="other",
                tags=[Tag.model_construct(name="bye", type="standalone")],
            )
        ],
    )

    merged = merge_tag_specs(base, overlay)

    assert [lib.module for lib in merged.libraries] == ["example", "other"]
