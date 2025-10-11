from __future__ import annotations

from djtagspecs.introspect import TemplateTag
from djtagspecs.introspect import get_installed_templatetags


def test_template_tag_dataclass():
    tag = TemplateTag(
        name="for",
        module="django.template.defaulttags",
        library=None,
    )
    assert tag.name == "for"
    assert tag.module == "django.template.defaulttags"
    assert tag.library is None


def test_template_tags_list():
    tags = [
        TemplateTag(name="for", module="django.template.defaulttags", library=None),
        TemplateTag(name="if", module="django.template.defaulttags", library=None),
    ]
    assert len(tags) == 2
    assert tags[0].name == "for"
    assert tags[1].name == "if"


def test_get_installed_templatetags_returns_list():
    result = get_installed_templatetags()
    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(tag, TemplateTag) for tag in result)


def test_get_installed_templatetags_includes_builtin_tags():
    result = get_installed_templatetags()
    tag_names = [tag.name for tag in result]

    assert "for" in tag_names
    assert "if" in tag_names
    assert "block" in tag_names
    assert "extends" in tag_names


def test_get_installed_templatetags_builtin_tags_have_no_library():
    result = get_installed_templatetags()
    builtin_tags = [tag for tag in result if tag.module.startswith("django.template.")]

    for tag in builtin_tags:
        assert tag.library is None


def test_get_installed_templatetags_includes_loadable_tags():
    result = get_installed_templatetags()
    loadable_tags = [tag for tag in result if tag.library is not None]

    assert len(loadable_tags) > 0
    tag_names = [tag.name for tag in loadable_tags]
    assert "static" in tag_names or "get_static_prefix" in tag_names


def test_get_installed_templatetags_loadable_tags_have_library_name():
    result = get_installed_templatetags()
    loadable_tags = [tag for tag in result if tag.library is not None]

    for tag in loadable_tags:
        assert tag.library is not None
        assert isinstance(tag.library, str)
        assert len(tag.library) > 0
