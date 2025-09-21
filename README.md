# djtagspecs

A specification for describing Django template tag syntax.

## What This Is and Is Not

✅ This IS:

- A **specification format** (like OpenAPI for APIs)
- A way to **document** template tag syntax
- A **standard** that tools can implement
- Reference models for **validating** TagSpec documents

❌ This is NOT:

- A template parser
- A tool that analyzes your Django templates  
- Something that generates output from templates
- A Django app you add to INSTALLED_APPS

Looking for a template parser? This isn't it. TagSpecs describes tag syntax so OTHER tools can parse templates correctly.

## Who Should Use This?

### 🔧 Tool Developers
Building a Django linter, language server, or documentation generator? Use TagSpecs to understand tag syntax without importing Django.

### 📚 Library Authors  
Maintain a custom template tag library? Write TagSpec documents so tools can understand your tags.

### 👩‍💻 Django Developers
Just writing Django apps? You probably don't need this directly—your tools will use it behind the scenes.

## The Problem TagSpecs Solves

Django template tags are powerful but opaque to static analysis:
- Each tag implements its own mini-parser
- Tools can't understand tag syntax without executing code
- No standard way to document tag structure

TagSpecs provides a declarative format to describe:
- What arguments a tag accepts
- Whether it's a block tag or standalone
- What intermediate tags are allowed (like elif/else)

## Quick Example

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

## How It Works

```
1. Django tag library authors write TagSpec documents
                       ↓
2. TagSpec documents describe tag syntax in TOML/JSON/YAML
                       ↓
3. Tools read TagSpec documents (NOT templates)
                       ↓
4. Tools use metadata to understand template syntax
                       ↓
5. Tools implement their own template parsing using this knowledge
                       ↓
6. End users get better IDE support, linting, etc.
```

**Key Point:** TagSpecs provides the metadata. Your tool does the actual template parsing.

## The Specification

📖 **[Read the full specification](spec/SPECIFICATION.md)**

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

1. **Discover** TagSpec documents (TOML/JSON/YAML)
2. **Validate** against the schema
3. **Use** the metadata to understand tag syntax
4. **Parse** templates using this knowledge (your code does this part!)

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

### Writing TagSpec Documents

If you're documenting your own template tags:

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

# or if you like the new hotness
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
A: This is machine-readable metadata, not human documentation.

**Q: Can I use this to generate documentation?**  
A: Yes! Tools can read TagSpec documents to auto-generate docs.

**Q: What if my tags have complex runtime behavior?**  
A: TagSpecs only describes syntax, not runtime semantics. Complex behavior stays in your code.

## Comparison to Other Specifications

| Specification | Domain | Purpose |
|--------------|--------|---------|
| OpenAPI | REST APIs | Describes API endpoints and schemas |
| JSON Schema | JSON data | Validates JSON structure |
| AsyncAPI | Event APIs | Describes async message APIs |
| GraphQL Schema | GraphQL APIs | Defines GraphQL types and operations |
| **TagSpecs** | Django tags | Describes template tag syntax |

All these specifications share a common goal: providing machine-readable metadata about an interface so tools can work with it without executing code.

## License

djtagspecs is licensed under the Apache License, Version 2.0. See the [`LICENSE`](LICENSE) file for more information.
