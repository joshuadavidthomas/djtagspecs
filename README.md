# djtagspecs

A specification for describing Django template tag syntax.

## Overview

TagSpecs is a machine-readable format for describing Django template tag syntax. If you're familiar with OpenAPI for REST APIs, TagSpecs plays a comparable role for Django templates: it captures the structure of tags so tooling can reason about them without executing Django itself.

The format emerged while I was building the [django-language-server](https://github.com/joshuadavidthomas/django-language-server). Trying to surface static diagnostics meant reverse-engineering a lot of hand-written parsing rules from Django core and third-party libraries. Writing those rules down as structured data turned out to be the repeatable part of the exercise, so I formalized the shape of that data here instead of letting it live only inside the language server’s codebase.

Publishing the spec is also an invitation to share catalogs of tag definitions. Externalizing the rules makes it possible to:

- avoid hard-coding template behaviour in every tool
- ship the same catalog with multiple tools or services
- describe custom tag libraries without touching code

TagSpecs documents can sit alongside libraries or be collected in a central catalog that multiple tools consume.

### What TagSpecs Provides

- A specification format, similar in spirit to OpenAPI or JSON Schema
- A way to document template tags so tools can understand them
- A catalog format that projects can publish and share
- A contract that tooling authors can implement against
- Backed by reference models for validating TagSpec documents

### What TagSpecs Does Not Provide

- A template parser
- A tool that analyzes templates or renders output
- A Django app to add to `INSTALLED_APPS`

If you are looking for something that parses templates, you need a separate tool. TagSpecs only supplies the metadata that tool would consume. The specification is new and currently powers the `django-language-server`; future tools are encouraged to adopt it.

## Audience

- Tool authors experimenting with linters, language servers, code intelligence, or documentation generators for Django templates
- Library maintainers who ship custom template tags and want to describe their syntax
- Django developers evaluating how template tooling could evolve or considering TagSpecs for a project of their own

## The Problem TagSpecs Solves

Django template tags are powerful but opaque to static analysis:
- Each tag implements its own mini-parser
- Tools can't understand tag syntax without executing code
- No standard way to document tag structure

TagSpecs provides a declarative format to describe:
- What arguments a tag accepts
- Whether it's a block tag or standalone
- What intermediate tags are allowed (like elif/else)

## Examples

### Documenting Django's `{% for %}` tag

Here's how Django's `{% for %}` tag is described in TagSpecs:

```toml
[[libraries.tags]]
name = "for"
type = "block"

[[libraries.tags.args]]
name = "items"
kind = "variable"

[[libraries.tags.intermediates]]
name = "empty"
max = 1
position = "last"

[libraries.tags.end]
name = "endfor"
```

This tells tools:
- `for` is a block tag ending with `endfor`
- It accepts a variable argument
- It can have an optional `empty` clause
- The `empty` clause must come last

Tools read this metadata to provide features like:
- Syntax highlighting
- Error detection (missing endfor, invalid empty placement)
- Auto-completion
- Documentation on hover

### Documenting your own tag library

Here's the structure for a custom `card` block tag:

```toml
version = "0.1.0"
engine = "django"

[[libraries]]
module = "myapp.templatetags.custom"

[[libraries.tags]]
name = "card"
type = "block"

[[libraries.tags.args]]
name = "title"
kind = "literal"
required = true

[libraries.tags.end]
name = "endcard"
```

This describes a single library (`myapp.templatetags.custom`) containing a `card` block tag. The tag requires a literal `title` argument and terminates with `endcard`.

## How It Works

Typical flow:

1. Template tag authors publish TagSpec documents
2. Documents describe tag syntax in TOML, JSON, or YAML
3. Tools read TagSpec documents (not templates) and validate them
4. Tools use the metadata to understand template structure
5. Tools implement their own template parsing logic using that information

TagSpecs provides structure only; parsing and analysis stay in your implementation.

Catalogs can travel with a tag library, live in a separate repository, or be bundled with tooling. The goal is to avoid scattering the same parsing rules across multiple codebases.

## Specification

Read the full specification: [spec/SPECIFICATION.md](spec/SPECIFICATION.md)

The specification defines:
- Document structure and fields
- Tag types (block, loader, standalone)
- Argument kinds and semantics
- Validation rules
- Extensibility mechanisms

### Specification and Schema

`djtagspecs` ships both the normative specification and a machine-readable schema so producers and tooling vendors can stay aligned.

- **Specification** – `spec/SPECIFICATION.md` is the authoritative contract for TagSpecs. It defines the object model, terminology, validation rules, and forward-compatibility guarantees that implementers MUST follow.
- **Schema** – `spec/schema.json` is generated from the Pydantic models and mirrors the specification. Use it to validate TagSpec documents or integrate with JSON Schema tooling.

## For Implementers

### Reading TagSpecs in Your Tool

1. Discover TagSpec documents (TOML, JSON, or YAML)
2. Validate them against the schema
3. Use the metadata to understand tag syntax
4. Implement parsing or analysis using that knowledge

### Example Implementation Pattern

```python
# Your tool loads TagSpecs (this library helps validate them)
from djtagspecs.models import TagSpec

spec = TagSpec.model_validate_json(...)

# Your tool uses the metadata to parse templates
# (TagSpecs doesn't do this part - that's YOUR implementation)
for tag in spec.libraries[0].tags:
    if tag.type == "block":
        # Your parser knows to look for end tag
        # Your parser validates intermediate tags
        # Your parser checks argument kinds
        ...
```

## Reference Implementation

### Python Package

We provide a Python package with:
- Pydantic models matching the specification
- JSON Schema generation
- Document validation

#### Requirements

- Python 3.10, 3.11, 3.12, 3.13

#### Installation

```bash
python -m pip install djtagspecs

# or with uv
uv add djtagspecs
uv sync
```

### CLI Tool

Generate JSON Schema for validation:

```bash
djts generate-schema -o schema.json
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

## Real-World Usage

TagSpecs was created for and powers the [django-language-server](https://github.com/joshuadavidthomas/django-language-server), which provides:
- Template diagnostics without importing user code
- Static validation of tag usage
- Auto-completion and hover documentation

The language server reads TagSpec documents to understand available tags, then uses that knowledge to analyze templates—all without executing Django code.

## FAQ

**Q: Does this parse my Django templates?**
A: No. It describes tag syntax so other tools can parse templates.

**Q: Do I need this for my Django project?**
A: Only if you're building tools or documenting a tag library.

**Q: Is this an official Django project?**
A: No, it's a community specification for tooling interoperability.

**Q: How is this different from Django's template documentation?**
A: TagSpecs is machine-readable metadata, not narrative documentation.

**Q: Can I use this to generate documentation?**
A: Yes. Tools can read TagSpec documents to generate docs.

**Q: What if my tags have complex runtime behavior?**
A: TagSpecs only describes syntax, not runtime semantics.

## License

djtagspecs is licensed under the Apache License, Version 2.0. See the [`LICENSE`](LICENSE) file for more information.
