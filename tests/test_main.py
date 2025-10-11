from __future__ import annotations

import csv
import io
import json

import pytest
from rich.table import Table
from typer.testing import CliRunner

from djtagspecs.__main__ import CoverageStats
from djtagspecs.__main__ import GroupBy
from djtagspecs.__main__ import SpecStatus
from djtagspecs.__main__ import app
from djtagspecs.__main__ import apply_filters
from djtagspecs.__main__ import calculate_coverage_stats
from djtagspecs.__main__ import format_as_csv
from djtagspecs.__main__ import format_as_json
from djtagspecs.__main__ import format_as_table
from djtagspecs.introspect import TemplateTag


class TestCoverageStats:
    def test_percentage_calculation(self):
        stats = CoverageStats(total=10, documented=5)
        assert stats.percentage == 50.0

        stats_full = CoverageStats(total=10, documented=10)
        assert stats_full.percentage == 100.0

        stats_none = CoverageStats(total=10, documented=0)
        assert stats_none.percentage == 0.0

    def test_zero_division_safe(self):
        stats = CoverageStats(total=0, documented=0)
        assert stats.percentage == 0.0

    def test_partial_coverage(self):
        stats = CoverageStats(total=3, documented=2)
        assert stats.percentage == pytest.approx(66.66666666666666)


class TestCalculateCoverageStats:
    def test_empty_list(self):
        overall, by_module = calculate_coverage_stats([])
        assert overall.total == 0
        assert overall.documented == 0
        assert by_module == {}

    def test_no_specs(self):
        tags = [
            TemplateTag("tag1", "module.a", None, has_spec=None),
            TemplateTag("tag2", "module.a", None, has_spec=False),
        ]
        overall, by_module = calculate_coverage_stats(tags)

        assert overall.total == 2
        assert overall.documented == 0

    def test_all_documented(self):
        tags = [
            TemplateTag("tag1", "module.a", None, has_spec=True),
            TemplateTag("tag2", "module.a", None, has_spec=True),
        ]
        overall, by_module = calculate_coverage_stats(tags)

        assert overall.total == 2
        assert overall.documented == 2
        assert overall.percentage == 100.0

    def test_mixed_coverage(self):
        tags = [
            TemplateTag("tag1", "module.a", None, has_spec=True),
            TemplateTag("tag2", "module.a", None, has_spec=False),
            TemplateTag("tag3", "module.b", None, has_spec=True),
        ]
        overall, by_module = calculate_coverage_stats(tags)

        assert overall.total == 3
        assert overall.documented == 2
        assert overall.percentage == pytest.approx(66.66666666666666)

        assert by_module["module.a"].total == 2
        assert by_module["module.a"].documented == 1
        assert by_module["module.a"].percentage == 50.0

        assert by_module["module.b"].total == 1
        assert by_module["module.b"].documented == 1
        assert by_module["module.b"].percentage == 100.0

    def test_multiple_modules(self):
        tags = [
            TemplateTag("tag1", "module.a", None, has_spec=True),
            TemplateTag("tag2", "module.b", None, has_spec=False),
            TemplateTag("tag3", "module.c", None, has_spec=True),
        ]
        overall, by_module = calculate_coverage_stats(tags)

        assert len(by_module) == 3
        assert "module.a" in by_module
        assert "module.b" in by_module
        assert "module.c" in by_module


class TestApplyFilters:
    def test_no_filters_returns_all(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None),
            TemplateTag("if", "django.template.defaulttags", None),
        ]
        result = apply_filters(tags)
        assert len(result) == 2

    def test_by_module_case_insensitive(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None),
            TemplateTag("custom", "myapp.tags", None),
        ]
        result = apply_filters(tags, module="DJANGO")
        assert len(result) == 1
        assert result[0].name == "for"

    def test_by_library_case_insensitive(self):
        tags = [
            TemplateTag("static", "django.templatetags.static", "static"),
            TemplateTag("custom", "myapp.tags", "mylib"),
        ]
        result = apply_filters(tags, library="STATIC")
        assert len(result) == 1
        assert result[0].name == "static"

    def test_by_name_case_insensitive(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None),
            TemplateTag("if", "django.template.defaulttags", None),
        ]
        result = apply_filters(tags, name="FOR")
        assert len(result) == 1
        assert result[0].name == "for"

    def test_status_missing(self):
        tags = [
            TemplateTag("tag1", "module.a", None, has_spec=True),
            TemplateTag("tag2", "module.a", None, has_spec=False),
            TemplateTag("tag3", "module.a", None, has_spec=None),
        ]
        result = apply_filters(tags, status=SpecStatus.MISSING)
        assert len(result) == 1
        assert result[0].name == "tag2"

    def test_status_documented(self):
        tags = [
            TemplateTag("tag1", "module.a", None, has_spec=True),
            TemplateTag("tag2", "module.a", None, has_spec=False),
            TemplateTag("tag3", "module.a", None, has_spec=None),
        ]
        result = apply_filters(tags, status=SpecStatus.DOCUMENTED)
        assert len(result) == 1
        assert result[0].name == "tag1"

    def test_status_all(self):
        tags = [
            TemplateTag("tag1", "module.a", None, has_spec=True),
            TemplateTag("tag2", "module.a", None, has_spec=False),
        ]
        result = apply_filters(tags, status=SpecStatus.ALL)
        assert len(result) == 2

    def test_multiple_filters_combined(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None),
            TemplateTag("if", "django.template.defaulttags", None),
            TemplateTag("custom", "myapp.tags", None),
        ]
        result = apply_filters(tags, module="django", name="for")
        assert len(result) == 1
        assert result[0].name == "for"

    def test_library_none_handling(self):
        tags = [
            TemplateTag("tag1", "module.a", None),
            TemplateTag("tag2", "module.a", "mylib"),
        ]
        result = apply_filters(tags, library="mylib")
        assert len(result) == 1
        assert result[0].library == "mylib"

    def test_partial_match(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None),
            TemplateTag("custom", "myapp.tags", None),
        ]
        result = apply_filters(tags, module="template")
        assert len(result) == 1
        assert result[0].name == "for"


class TestFormatAsJson:
    def test_returns_valid_json(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None, has_spec=True),
        ]
        output = format_as_json(tags)
        data = json.loads(output)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "for"
        assert data[0]["module"] == "django.template.defaulttags"
        assert data[0]["library"] is None
        assert data[0]["has_spec"] is True

    def test_empty_list(self):
        output = format_as_json([])
        data = json.loads(output)
        assert data == []

    def test_includes_all_fields(self):
        tags = [
            TemplateTag(
                "static", "django.templatetags.static", "static", has_spec=False
            ),
        ]
        output = format_as_json(tags)
        data = json.loads(output)

        assert "name" in data[0]
        assert "module" in data[0]
        assert "library" in data[0]
        assert "has_spec" in data[0]

    def test_none_values_serialized_as_null(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None, has_spec=None),
        ]
        output = format_as_json(tags)

        assert '"library": null' in output
        assert '"has_spec": null' in output
        assert '"None"' not in output

    def test_formatted_with_indent(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None),
        ]
        output = format_as_json(tags)
        assert "\n" in output

    def test_group_by_module_returns_list(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None),
            TemplateTag("static", "django.templatetags.static", "static"),
        ]
        output = format_as_json(tags, GroupBy.MODULE)
        data = json.loads(output)

        assert isinstance(data, list)
        assert len(data) == 2

    def test_group_by_package_returns_dict(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None),
            TemplateTag("static", "django.templatetags.static", "static"),
            TemplateTag("custom", "myapp.templatetags.tags", None),
        ]
        output = format_as_json(tags, GroupBy.PACKAGE)
        data = json.loads(output)

        assert isinstance(data, dict)
        assert "django" in data
        assert "myapp" in data
        assert len(data["django"]) == 2
        assert len(data["myapp"]) == 1
        assert data["django"][0]["name"] == "for"
        assert data["django"][1]["name"] == "static"
        assert data["myapp"][0]["name"] == "custom"


class TestFormatAsCsv:
    def test_header_row(self):
        tags = [TemplateTag("for", "django.template.defaulttags", None)]

        csv_content = format_as_csv(tags)
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        assert rows[0] == ["name", "module", "library", "has_spec"]

    def test_empty_list(self):
        csv_content = format_as_csv([])
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 1
        assert rows[0] == ["name", "module", "library", "has_spec"]

    def test_data_rows(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None, has_spec=True),
        ]

        csv_content = format_as_csv(tags)
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 2
        assert rows[1] == ["for", "django.template.defaulttags", "", "True"]

    def test_none_values_as_empty_strings(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None, has_spec=None),
        ]

        csv_content = format_as_csv(tags)
        lines = csv_content.strip().split("\n")

        assert "None" not in lines[1]
        assert '"None"' not in lines[1]

    def test_special_characters_escaped(self):
        tags = [
            TemplateTag("tag,with,commas", "module.a", "lib,with,commas"),
        ]

        csv_content = format_as_csv(tags)
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        assert rows[1][0] == "tag,with,commas"
        assert rows[1][2] == "lib,with,commas"

    def test_group_by_module_header(self):
        tags = [TemplateTag("for", "django.template.defaulttags", None)]

        csv_content = format_as_csv(tags, GroupBy.MODULE)
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        assert rows[0] == ["name", "module", "library", "has_spec"]

    def test_group_by_package_header(self):
        tags = [TemplateTag("for", "django.template.defaulttags", None)]

        csv_content = format_as_csv(tags, GroupBy.PACKAGE)
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        assert rows[0] == ["package", "name", "module", "library", "has_spec"]

    def test_group_by_package_includes_package_column(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None),
            TemplateTag("custom", "myapp.templatetags.tags", None),
        ]

        csv_content = format_as_csv(tags, GroupBy.PACKAGE)
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 3
        assert rows[1][0] == "django"
        assert rows[1][1] == "for"
        assert rows[2][0] == "myapp"
        assert rows[2][1] == "custom"


class TestFormatAsTable:
    def test_without_catalog_returns_tables(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None),
            TemplateTag("if", "django.template.defaulttags", None),
        ]
        printables = format_as_table(tags, catalog=None)

        assert isinstance(printables, list)
        assert len(printables) == 1
        assert isinstance(printables[0], Table)

    def test_without_catalog_no_spec_column(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None),
        ]
        printables = format_as_table(tags, catalog=None)

        table = printables[0]
        assert isinstance(table, Table)
        column_headers = [col.header for col in table.columns]
        assert "Spec" not in column_headers

    def test_with_catalog_returns_coverage(self, tmp_path):
        catalog = tmp_path / "catalog.toml"
        catalog.write_text(
            """
[[libraries]]
module = "django.template.defaulttags"

[[libraries.tags]]
name = "for"
type = "standalone"
        """.strip()
        )

        tags = [
            TemplateTag("for", "django.template.defaulttags", None, has_spec=True),
            TemplateTag("if", "django.template.defaulttags", None, has_spec=False),
        ]
        printables = format_as_table(tags, catalog=catalog)

        assert isinstance(printables, list)
        assert len(printables) == 3
        assert isinstance(printables[0], Table)
        assert isinstance(printables[1], str)
        assert "Overall Coverage" in printables[1]
        assert isinstance(printables[2], Table)

    def test_with_catalog_has_spec_column(self, tmp_path):
        catalog = tmp_path / "catalog.toml"
        catalog.write_text(
            """
[[libraries]]
module = "django.template.defaulttags"

[[libraries.tags]]
name = "for"
type = "standalone"
        """.strip()
        )

        tags = [
            TemplateTag("for", "django.template.defaulttags", None, has_spec=True),
        ]
        printables = format_as_table(tags, catalog=catalog)

        table = printables[0]
        assert isinstance(table, Table)
        column_headers = [col.header for col in table.columns]
        assert "Spec" in column_headers

    def test_groups_by_module(self):
        tags = [
            TemplateTag("for", "django.template.defaulttags", None),
            TemplateTag("custom", "myapp.tags", None),
        ]
        printables = format_as_table(tags, catalog=None)

        tables = [p for p in printables if isinstance(p, Table)]
        assert len(tables) == 2

    def test_sorts_by_module_and_name(self):
        tags = [
            TemplateTag("zebra", "module.b", None),
            TemplateTag("apple", "module.a", None),
            TemplateTag("banana", "module.a", None),
        ]
        printables = format_as_table(tags, catalog=None)

        tables = [p for p in printables if isinstance(p, Table)]
        assert len(tables) == 2

    def test_library_column_conditional(self):
        tags_no_library = [
            TemplateTag("for", "django.template.defaulttags", None),
        ]
        printables_no_lib = format_as_table(tags_no_library, catalog=None)
        table_no_lib = printables_no_lib[0]
        assert isinstance(table_no_lib, Table)
        columns_no_lib = [col.header for col in table_no_lib.columns]
        assert "Library" not in columns_no_lib

        tags_with_library = [
            TemplateTag("static", "django.templatetags.static", "static"),
        ]
        printables_with_lib = format_as_table(tags_with_library, catalog=None)
        table_with_lib = printables_with_lib[0]
        assert isinstance(table_with_lib, Table)
        columns_with_lib = [col.header for col in table_with_lib.columns]
        assert "Library" in columns_with_lib

    def test_empty_list(self):
        printables = format_as_table([], catalog=None)

        assert printables == []

    def test_group_by_module_default(self):
        tags = [
            TemplateTag("tag1", "django.template.defaulttags", None),
            TemplateTag("tag2", "django.contrib.humanize.templatetags.humanize", None),
        ]
        printables = format_as_table(tags, catalog=None, group_by=GroupBy.MODULE)

        tables = [p for p in printables if isinstance(p, Table)]
        assert len(tables) == 2

    def test_group_by_package(self):
        tags = [
            TemplateTag("tag1", "django.template.defaulttags", None),
            TemplateTag("tag2", "django.contrib.humanize.templatetags.humanize", None),
            TemplateTag("tag3", "myapp.templatetags.tags", None),
        ]
        printables = format_as_table(tags, catalog=None, group_by=GroupBy.PACKAGE)

        tables = [p for p in printables if isinstance(p, Table)]
        assert len(tables) == 2


class TestListTagsCommand:
    def test_json_format(self):
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "list-tags",
                "--format",
                "json",
                "--module",
                "django.template.defaulttags",
                "--name",
                "for",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_csv_format(self):
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "list-tags",
                "--format",
                "csv",
                "--module",
                "django.template.defaulttags",
                "--name",
                "for",
            ],
        )
        assert result.exit_code == 0
        lines = result.stdout.strip().split("\n")
        assert lines[0] == "name,module,library,has_spec"

    def test_table_format_default(self):
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "list-tags",
                "--module",
                "django.template.defaulttags",
                "--name",
                "for",
            ],
        )
        assert result.exit_code == 0
        assert "django.template.defaulttags" in result.stdout

    def test_with_filters(self):
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "list-tags",
                "--format",
                "json",
                "--module",
                "django",
                "--name",
                "for",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        for tag in data:
            assert "django" in tag["module"].lower()
            assert "for" in tag["name"].lower()

    def test_status_requires_catalog(self):
        runner = CliRunner()
        result = runner.invoke(app, ["list-tags", "--status", "documented"])
        assert result.exit_code == 1
        assert "requires --catalog" in result.stderr

    def test_no_results(self):
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "list-tags",
                "--module",
                "nonexistent_module_that_does_not_exist",
            ],
        )
        assert result.exit_code == 0
        assert "No tags found" in result.stdout

    def test_with_catalog(self, tmp_path):
        catalog = tmp_path / "catalog.toml"
        catalog.write_text(
            """
[[libraries]]
module = "django.template.defaulttags"

[[libraries.tags]]
name = "for"
type = "standalone"

[[libraries.tags]]
name = "if"
type = "standalone"

[[libraries.tags]]
name = "autoescape"
type = "block"
        """.strip()
        )

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "list-tags",
                "--catalog",
                str(catalog),
                "--module",
                "django.template.defaulttags",
            ],
        )
        assert result.exit_code == 0
        assert "Coverage:" in result.stdout
        assert "Overall Coverage:" in result.stdout
