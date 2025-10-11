from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import django
from django.apps import apps
from django.template.engine import Engine
from django.template.library import import_library

from djtagspecs.catalog import load_tag_spec


@dataclass
class TemplateTag:
    name: str
    module: str
    library: str | None
    has_spec: bool | None = None


TemplateTags = list[TemplateTag]


def get_installed_templatetags() -> TemplateTags:
    if not apps.ready:
        django.setup()

    templatetags: TemplateTags = []
    engine = Engine.get_default()

    for library in engine.template_builtins:
        if library.tags:
            for tag_name, tag_func in library.tags.items():
                templatetags.append(
                    TemplateTag(
                        name=tag_name,
                        module=tag_func.__module__,
                        library=None,
                    )
                )

    for lib_module in engine.libraries.values():
        library = import_library(lib_module)
        if library and library.tags:
            lib_name = None
            for lib_name_candidate, lib_module_candidate in engine.libraries.items():
                if lib_module_candidate == lib_module or lib_module.endswith(
                    f".{lib_module_candidate}"
                ):
                    lib_name = lib_name_candidate
                    break

            if lib_name is None and ".templatetags." in lib_module:
                parts = lib_module.split(".templatetags.")
                if len(parts) == 2:
                    lib_name = parts[1]

            for tag_name, tag_func in library.tags.items():
                templatetags.append(
                    TemplateTag(
                        name=tag_name,
                        module=tag_func.__module__,
                        library=lib_name,
                    )
                )

    return templatetags


def annotate_with_specs(tags: TemplateTags, catalog_path: Path | str) -> TemplateTags:
    catalog_path = Path(catalog_path)
    spec = load_tag_spec(catalog_path)

    spec_lookup: set[tuple[str, str]] = set()
    for library in spec.libraries:
        for spec_tag in library.tags:
            spec_lookup.add((library.module, spec_tag.name))

    annotated_tags = []
    for tag in tags:
        has_spec = (tag.module, tag.name) in spec_lookup
        annotated_tags.append(
            TemplateTag(
                name=tag.name,
                module=tag.module,
                library=tag.library,
                has_spec=has_spec,
            )
        )

    return annotated_tags
