# djtagspecs

Structured metadata for Django-style template tags. `djtagspecs` provides the TagSpecs specification, a reference JSON Schema, and a small CLI so tooling can reason about template syntax without importing Django or executing tag code.

## Specification and Schema

`djtagspecs` ships both the normative specification and a machine-readable schema so producers and tooling vendors can stay aligned.

- **Specification** – `spec/SPECIFICATION.md` is the authoritative contract for TagSpecs. It defines the object model, terminology, validation rules, and forward-compatibility guarantees that implementers MUST follow.
- **Schema** – `spec/schema.json` is generated from the Pydantic models and mirrors the specification. Use it to validate TagSpec documents or integrate with JSON Schema tooling.

Regenerate the schema whenever the models change to keep distribution artifacts in sync:

```bash
djts generate-schema -o spec/schema.json
```

If discrepancies arise, the written specification takes precedence; the schema is an executable companion for tooling convenience.

## Library

### Features

- Describe tag libraries, arguments, block structure, and semantics in a declarative format.
- Publish machine-readable specs that static analysers and editors can ingest.
- Generate a canonical JSON Schema for validation or documentation tooling.

### Requirements

- Python 3.10, 3.11, 3.12, 3.13

### Installation

```bash
python -m pip install djtagspecs

# or if you like the new hotness

uv add djtagspecs
uv sync
```

### CLI usage

The package exposes the `djts` CLI. Use it to emit the reference schema:

```bash
djts generate-schema -o spec/schema.json
```

Omit `-o` to print the schema to stdout. The command guarantees the emitted schema matches the Pydantic models shipped in this distribution.

### Python API

The Pydantic models in `djtagspecs.models` mirror the specification. Example:

```python
from pathlib import Path

from djtagspecs.models import TagSpec

spec_path = Path("spec/catalog.json")
catalog = TagSpec.model_validate_json(spec_path.read_text())
print(catalog.engine)
```

The models apply defaults and validate the structure of TagSpec documents. Any unknown keys are preserved so specs can round-trip safely.

## License

djtagspecs is licensed under the Apache License, Version 2.0. See the [`LICENSE`](LICENSE) file for more information.
