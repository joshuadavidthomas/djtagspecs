from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from dataclasses import asdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated
from typing import Any

import typer
from pydantic.json_schema import GenerateJsonSchema
from pydantic.json_schema import JsonSchemaMode
from pydantic_core import CoreSchema
from rich.console import Console
from rich.table import Table

from djtagspecs._typing import override
from djtagspecs.catalog import TagSpecError
from djtagspecs.catalog import TagSpecFormat
from djtagspecs.catalog import dump_tag_spec
from djtagspecs.catalog import load_tag_spec
from djtagspecs.introspect import TemplateTags
from djtagspecs.introspect import annotate_with_specs
from djtagspecs.introspect import get_installed_templatetags
from djtagspecs.models import TagSpec

app = typer.Typer(
    name="djts",
    help="Utilities for working with Django TagSpecs.",
    no_args_is_help=True,
)


@app.callback()
def cli() -> None:
    """Command-line interface for Django TagSpecs."""


class GenerateTagSpecJsonSchema(GenerateJsonSchema):
    @override
    def generate(self, schema: CoreSchema, mode: JsonSchemaMode = "validation"):
        json_schema = super().generate(schema, mode=mode)
        json_schema["$schema"] = self.schema_dialect
        return json_schema


@app.command(
    "generate-schema", help="Emit the TagSpec JSON Schema to stdout or a file."
)
def generate_schema(
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            exists=False,
            file_okay=True,
            dir_okay=False,
            writable=True,
            resolve_path=True,
            help="Optional path to write the generated schema. Defaults to stdout.",
        ),
    ] = None,
) -> None:
    schema = TagSpec.model_json_schema(schema_generator=GenerateTagSpecJsonSchema)
    payload = json.dumps(schema, indent=2, sort_keys=True)

    if output is None:
        typer.echo(payload)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")


@app.command(help="Validate a TagSpec document and report any issues.")
def validate(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            file_okay=True,
            readable=True,
            resolve_path=True,
            help="Path to the TagSpec document to validate.",
        ),
    ],
    resolve_extends: Annotated[
        bool,
        typer.Option(
            "--resolve/--no-resolve",
            help="Whether to resolve the document's extends chain before validation.",
        ),
    ] = True,
) -> None:
    try:
        load_tag_spec(path, resolve_extends=resolve_extends)
    except TagSpecError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho("Document is valid.", fg=typer.colors.GREEN)


@app.command(help="Resolve a TagSpec document and write the flattened result.")
def flatten(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            file_okay=True,
            readable=True,
            resolve_path=True,
            help="Path to the TagSpec document to resolve.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            exists=False,
            dir_okay=False,
            file_okay=True,
            writable=True,
            resolve_path=True,
            help="Destination to write the flattened document. Defaults to stdout.",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            case_sensitive=False,
            help="Serialisation format for output (toml or json).",
        ),
    ] = "toml",
) -> None:
    try:
        spec = load_tag_spec(path, resolve_extends=True)
    except TagSpecError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    try:
        output_format = TagSpecFormat.coerce(format)
    except TagSpecError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if output is None:
        typer.echo(dump_tag_spec(spec, format=output_format))
    else:
        payload = dump_tag_spec(spec, format=output_format)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        typer.secho(f"Wrote flattened document to {output}", fg=typer.colors.GREEN)


class OutputFormat(str, Enum):
    TABLE = "table"
    JSON = "json"
    CSV = "csv"


class SpecStatus(str, Enum):
    ALL = "all"
    MISSING = "missing"
    DOCUMENTED = "documented"


class GroupBy(str, Enum):
    MODULE = "module"
    PACKAGE = "package"


@dataclass
class CoverageStats:
    total: int
    documented: int

    @property
    def percentage(self) -> float:
        return (self.documented / self.total * 100) if self.total > 0 else 0.0


def calculate_coverage_stats(
    tags: TemplateTags,
) -> tuple[CoverageStats, dict[str, CoverageStats]]:
    overall = CoverageStats(total=0, documented=0)
    by_module: dict[str, CoverageStats] = {}

    for tag in tags:
        overall.total += 1
        if tag.module not in by_module:
            by_module[tag.module] = CoverageStats(total=0, documented=0)
        by_module[tag.module].total += 1

        if tag.has_spec is True:
            overall.documented += 1
            by_module[tag.module].documented += 1

    return overall, by_module


def apply_filters(
    tags: TemplateTags,
    module: str | None = None,
    library: str | None = None,
    name: str | None = None,
    status: SpecStatus = SpecStatus.ALL,
) -> TemplateTags:
    return [
        t
        for t in tags
        if (not module or module.lower() in t.module.lower())
        and (not library or (t.library and library.lower() in t.library.lower()))
        and (not name or name.lower() in t.name.lower())
        and (
            status == SpecStatus.ALL
            or (status == SpecStatus.MISSING and t.has_spec is False)
            or (status == SpecStatus.DOCUMENTED and t.has_spec is True)
        )
    ]


def format_as_json(
    tags: TemplateTags, group_by: GroupBy = GroupBy.MODULE, indent: int = 2
) -> str:
    if group_by == GroupBy.MODULE:
        return json.dumps([asdict(t) for t in tags], indent=indent)

    data: dict[str, list[dict[str, Any]]] = {}
    for t in tags:
        package = t.module.split(".")[0]
        if package not in data:
            data[package] = []
        data[package].append(asdict(t))
    return json.dumps(data, indent=indent)


def format_as_csv(tags: TemplateTags, group_by: GroupBy = GroupBy.MODULE) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    headers = ["name", "module", "library", "has_spec"]
    if group_by == GroupBy.PACKAGE:
        headers.insert(0, "package")
    writer.writerow(headers)

    for tag in tags:
        row = [tag.name, tag.module, tag.library or "", tag.has_spec or ""]
        if group_by == GroupBy.PACKAGE:
            row.insert(0, tag.module.split(".")[0])
        writer.writerow(row)

    return output.getvalue()


def format_as_printables(
    tags: TemplateTags,
    catalog: Path | None,
    group_by: GroupBy = GroupBy.MODULE,
) -> list[Table | str]:
    grouped: dict[str, TemplateTags] = defaultdict(list)
    for tag in sorted(tags, key=lambda t: (t.module, t.name)):
        key = tag.module if group_by == GroupBy.MODULE else tag.module.split(".")[0]
        grouped[key].append(tag)

    overall: CoverageStats | None = None
    by_module: dict[str, CoverageStats] = {}
    if catalog:
        overall, by_module = calculate_coverage_stats(tags)

    printables: list[Table | str] = []

    for mod in sorted(grouped.keys()):
        mod_tags = grouped[mod]

        if catalog and mod in by_module:
            mod_stats = by_module[mod]
            table = Table(
                title=f"[bold cyan]{mod}[/bold cyan]",
                caption=f"Coverage: {mod_stats.documented}/{mod_stats.total} tags",
                show_header=True,
                header_style="bold magenta",
                min_width=60,
            )
        else:
            table = Table(
                title=f"[bold cyan]{mod}[/bold cyan]",
                show_header=True,
                header_style="bold magenta",
                min_width=60,
            )

        table.add_column("Tag", style="cyan", no_wrap=True, min_width=40)

        if any(t.library for t in mod_tags):
            table.add_column("Library", style="yellow", no_wrap=True)

        if catalog:
            table.add_column("Spec", justify="center", no_wrap=True)

        for tag in mod_tags:
            row = [tag.name]

            if any(t.library for t in mod_tags):
                row.append(tag.library or "")

            if catalog:
                spec_indicator = "✓" if tag.has_spec else "✗"
                spec_style = "green" if tag.has_spec else "red"
                row.append(f"[{spec_style}]{spec_indicator}[/{spec_style}]")

            table.add_row(*row)

        printables.append(table)

    if catalog and by_module and overall:
        printables.append(
            f"\n[bold]Overall Coverage:[/bold] {overall.documented}/{overall.total} tags ({overall.percentage:.1f}%)"
        )

        summary_table = Table(
            title="[bold]Coverage by Module[/bold]",
            show_header=True,
            header_style="bold magenta",
        )
        summary_table.add_column("Module", style="cyan", no_wrap=True)
        summary_table.add_column("Coverage", justify="right")
        summary_table.add_column("Percent", justify="right")

        for mod in sorted(grouped.keys()):
            mod_stats = by_module[mod]
            pct_style = (
                "green"
                if mod_stats.percentage == 100
                else "yellow"
                if mod_stats.percentage > 0
                else "red"
            )
            summary_table.add_row(
                mod,
                f"{mod_stats.documented}/{mod_stats.total}",
                f"[{pct_style}]{mod_stats.percentage:.1f}%[/{pct_style}]",
            )

        printables.append(summary_table)

    return printables


@app.command(
    name="list-tags", help="List all Django template tags installed in the environment."
)
def list_tags(
    catalog: Annotated[
        Path | None,
        typer.Option(
            "--catalog",
            "-c",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="TagSpec catalog to check coverage against",
        ),
    ] = None,
    module: Annotated[
        str | None,
        typer.Option("--module", "-m", help="Filter by module name pattern"),
    ] = None,
    library: Annotated[
        str | None,
        typer.Option("--library", "-l", help="Filter by library name"),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Filter by tag name pattern"),
    ] = None,
    status: Annotated[
        SpecStatus,
        typer.Option(
            "--status",
            help="Filter tags by TagSpec status (requires --catalog when not 'all')",
            case_sensitive=False,
        ),
    ] = SpecStatus.ALL,
    format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            help="Output format",
            case_sensitive=False,
        ),
    ] = OutputFormat.TABLE,
    group_by: Annotated[
        GroupBy,
        typer.Option(
            "--group-by",
            help="Group tags by module or package",
            case_sensitive=False,
        ),
    ] = GroupBy.MODULE,
) -> None:
    if status != SpecStatus.ALL and not catalog:
        typer.secho(
            "Error: --status missing/documented requires --catalog to be specified.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    tags = get_installed_templatetags()

    if catalog:
        try:
            tags = annotate_with_specs(tags, catalog)
        except TagSpecError as exc:
            typer.secho(f"Error loading catalog: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc

    tags = apply_filters(
        tags,
        module=module,
        library=library,
        name=name,
        status=status,
    )

    if not tags:
        typer.secho("No tags found matching the criteria.", fg=typer.colors.YELLOW)
        return

    if format == OutputFormat.JSON:
        typer.echo(format_as_json(tags, group_by))
    elif format == OutputFormat.CSV:
        typer.echo(format_as_csv(tags, group_by), nl=False)
    else:
        console = Console()
        printables = format_as_printables(tags, catalog, group_by)

        for item in printables:
            console.print()
            console.print(item)


if __name__ == "__main__":
    app()
