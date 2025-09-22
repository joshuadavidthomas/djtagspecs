from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic.json_schema import GenerateJsonSchema
from pydantic.json_schema import JsonSchemaMode
from pydantic_core import CoreSchema

from djtagspecs._typing import override
from djtagspecs.catalog import TagSpecError
from djtagspecs.catalog import TagSpecFormat
from djtagspecs.catalog import dump_tag_spec
from djtagspecs.catalog import load_tag_spec
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


if __name__ == "__main__":
    app()
