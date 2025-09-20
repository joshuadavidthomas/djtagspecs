from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated
from typing import Optional
from typing import override

import typer
from pydantic.json_schema import GenerateJsonSchema
from pydantic.json_schema import JsonSchemaMode
from pydantic_core import CoreSchema

from django_tagspecs.models import TagSpec


app = typer.Typer(
    name="djts",
    help="Utilities for working with Django TagSpecs.",
    no_args_is_help=True,
)


@app.callback()
def cli() -> None:
    """Command-line interface for Django TagSpecs."""
    # The callback intentionally does nothing; subcommands provide functionality.
    return None


class GenerateTagSpecJsonSchema(GenerateJsonSchema):
    @override
    def generate(self, schema: CoreSchema, mode: JsonSchemaMode = "validation"):
        json_schema = super().generate(schema, mode=mode)
        json_schema["$schema"] = self.schema_dialect
        return json_schema


@app.command("generate-schema", help="Emit the TagSpec JSON Schema to stdout or a file.")
def generate_schema(
    output: Annotated[
        Optional[Path],
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
    payload = json.dumps(schema, indent=2)

    if output is None:
        typer.echo(payload)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
