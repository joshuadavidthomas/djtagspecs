# djtagspecs

A specification for describing Django template tag syntax.

## Overview

TagSpecs is a machine-readable format for describing Django template tag syntax. 

If you're familiar with OpenAPI for REST APIs, TagSpecs plays a comparable role for Django templates: it captures the structure of tags so tools can reason about them without importing Django or executing tag code.

The format is designed to live alongside Django rather than inside it. It documents tag syntax, structure, and semantics so tooling can perform static analysis without involving the Django runtime. 

TagSpecs is intended to complement Django and is primarily for the people building tooling around the template system—language servers, linters, documentation generators, and similar projects.

### So, What Is It?

OK, ok... I know that still doesn't really answer the “what is it?” question. 

In basic terms, TagSpecs is a specification format for describing Django template tags, a shareable catalog you can publish alongside your tag library, and a set of reference models that help tools validate those documents. It is external to Django, aimed at people building template-aware tooling.

It is not a template parser, a drop-in Django package, or an analyzer that ships ready-made template insights. TagSpecs just describes syntax, structure, and semantics.

That makes it most useful for people building Django-aware tooling or shipping custom tag libraries. Document your tags once, publish the catalog, and let multiple tools consume the same metadata. If you’re experimenting with linters, language servers, or documentation generators—or maintaining custom tag libraries—you’re the audience. If you only use built-in tags or want a new rendering engine, this probably isn’t for you.

### Wait, So What Do I Do With It?

If you’re a day-to-day Django developer, you can mostly keep scrolling. TagSpecs exists so tooling can understand templates without running them; your benefit comes when the tools you already use adopt the spec.

If you maintain a third-party library that ships template tags, TagSpecs lets you document their syntax once and share that definition with any tool that cares.

If you build tools around Django templates—linters, formatters, language servers, doc generators—TagSpecs is the contract you can publish instead of baking parsing rules into your codebase.

Still confused? Skip to the [examples](#examples) to see what a TagSpec document looks like in practice.

## Motivation

I stumbled into the rules and confif that lead to the TagSpec specification while working on [django-language-server](https://github.com/joshuadavidthomas/django-language-server). The goal was to surface diagnostics statically without importing Django or executing user code.

The first approach was straightforward but brittle, hard-coding the behaviour of Django’s built-in tags. That plan fell apart once I thought about third-party libraries and custom tags. There’s no limit to how many exist in the wild, and baking the rules into a language server both doesn't scale *and* filled me with a sense of dread as I thought of the sheer amount of work it would take.

The only durable part of the work was writing the rules down. Once tag syntax, block structure, and semantics lived in a structured document, the language server could reuse them. That repeatable bit turned into TagSpecs: a declarative format that captures the knowledge instead of the code that interprets it.

Publishing the specification outside the language server keeps those rules from being an internal detail. Library authors can ship their own TagSpec documents, tooling authors can exchange catalogs instead of reverse-engineering each other’s heuristics, and curious Django developers get a shared vocabulary. The more people who publish and consume TagSpecs, the better the tooling ecosystem becomes.

## Real-World Usage

TagSpecs was created for and powers the [django-language-server](https://github.com/joshuadavidthomas/django-language-server), which provides template diagnostics without importing user code and static validation of tag usage. 

The language server reads TagSpec documents to understand available tags, then uses that knowledge to analyze templates—all without executing Django code.

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

## Using TagSpecs

### Typical Flow

1. Template tag authors publish TagSpec documents
2. Documents describe tag syntax in TOML, JSON, or YAML
3. Tools read TagSpec documents (not templates) and validate them
4. Tools use the metadata to understand template structure
5. Tools implement their own template parsing logic using that information

TagSpecs provides structure only; parsing and analysis stay in your implementation.

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

## Specification & Schema

Read the full specification: [spec/SPECIFICATION.md](spec/SPECIFICATION.md)

The specification defines:
- Document structure and fields
- Tag types (block, loader, standalone)
- Argument kinds and semantics
- Validation rules
- Extensibility mechanisms

`djtagspecs` ships both the normative specification and a machine-readable schema so producers and tooling vendors can stay aligned:

- **Specification** – `spec/SPECIFICATION.md` is the authoritative contract for TagSpecs. It defines the object model, terminology, validation rules, and forward-compatibility guarantees that implementers MUST follow.
- **Schema** – `spec/schema.json` is generated from the Pydantic models and mirrors the specification. Use it to validate TagSpec documents or integrate with JSON Schema tooling.

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

## FAQ

**Q: Does this parse my Django templates?**<br />
A: No. It describes tag syntax so other tools can parse templates.

**Q: Do I need this for my Django project?**<br />
A: Only if you're building tools or documenting a tag library.

**Q: Is this an official Django project?**<br />
A: No, it's a community specification for tooling interoperability.

**Q: How is this different from Django's template documentation?**<br />
A: TagSpecs is machine-readable metadata, not narrative documentation.

**Q: Can I use this to generate documentation?**<br />
A: Yes. Tools can read TagSpec documents to generate docs.

**Q: What if my tags have complex runtime behavior?**<br />
A: TagSpecs only describes syntax, not runtime semantics.

## License

djtagspecs is licensed under the Apache License, Version 2.0. See the [`LICENSE`](LICENSE) file for more information.
