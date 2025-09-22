# djtagspecs

A specification for describing Django template tag syntax.

## Overview

TagSpec is a machine-readable format for describing Django template tag syntax. 

If you're familiar with OpenAPI for REST APIs, the TagSpec specification plays a comparable role for Django templates: it captures the structure of tags so tools can reason about them without importing Django or executing tag code.

The format is designed to live alongside Django rather than inside it. It documents tag syntax, structure, and semantics so tooling can perform static analysis without involving the Django runtime. 

TagSpecs are intended to complement Django and are primarily for the people building tooling around the template system, e.g., language servers, linters, documentation generators, and similar projects.

### So, What Is It?

OK, ok... I know that still doesn't really answer the “what is it?” question. 

In basic terms, TagSpecs are a specification format for describing Django template tags, a shareable catalog you can publish alongside your tag library, and a set of reference models that help tools validate those documents. It is external to Django, aimed at people building template-aware tooling.

It is not a template parser, a drop-in Django package, or an analyzer that ships ready-made template insights. TagSpecs just describe syntax, structure, and (through use of an `extra` field) semantics.

That makes it most useful for people building Django-aware tooling or shipping custom tag libraries. Document your tags once, publish the catalog, and let multiple tools consume the same metadata.

### Wait, So What Do I Do With It?

If you’re a day-to-day Django developer, you can mostly keep scrolling. TagSpecs exist so tooling can understand templates without running them. Your benefit comes when the tools you already use adopt the spec.

If you maintain a third-party library that ships template tags, TagSpecs let you document their syntax once and share that definition with any tool that cares.

If you build tools around Django templates, TagSpecs are the contract you can publish instead of baking parsing rules into your codebase.

Still confused? Skip to the [examples](#examples) to see what a TagSpec document looks like in practice.

## Motivation

I stumbled into the rules and config that lead to the TagSpec specification while working on [django-language-server](https://github.com/joshuadavidthomas/django-language-server). The goal was to surface diagnostics statically without importing Django or executing user code.

The first approach was straightforward but brittle, hard-coding the behaviour of Django’s built-in tags. That plan fell apart once I thought about third-party libraries and custom tags. There’s no limit to how many exist in the wild, and baking the rules into a language server both doesn’t scale *and* filled me with a sense of dread at the sheer amount of work it would take.

See, the template engine is hands-off when it comes to template tags. You can pretty much do whatever you want inside one as long as you return a string when it renders. That flexibility is great for authors but makes developing AST-style heuristics almost impossible (if you have any ideas on how to do so, please let me know!). Even the name of an end tag is just convention, Django doesn’t enforce `end<tag_name>`.

But if you step back and think about the pieces you actually need to validate usage, the list is surprisingly small: the tag’s name, the arguments it accepts, whether it requires a closing tag, and which intermediate tags are allowed before that closing tag.

Once that clicked, the only hard part of the work was writing the rules down. Capture the syntax, block structure, and semantics in a structured document and the language server can reuse it. That repeatable bit turned into the specification contained in this repository: a declarative format that stores the knowledge instead of the code that interprets it.

Publishing the specification outside the language server keeps those rules from being an internal detail. The end goal is library authors can ship their own TagSpec documents, tooling authors can swap catalogs instead of each crafting bespoke parsing logic, and curious Django developers get a shared vocabulary.

## Real-World Usage

TagSpecs was created for—and powers—the [django-language-server](https://github.com/joshuadavidthomas/django-language-server). The language server reads TagSpec documents to understand available tags, then uses that knowledge to analyse templates without importing user code or executing Django.

## FAQ

**Q: I'm still confused, how exactly do I use this library?**<br />
A: Well, you don't exactly. The specification describes a set of rules for statically defining Django template tags so that tools can parse and validate them. This repository contains that specification and a minimal Python library with the reference specification as Pydantic models.

**Q: Does this parse my Django templates?**<br />
A: No. It describes tag syntax so other tools can parse templates.

**Q: Do I need this for my Django project?**<br />
A: Only if you're building tools or documenting a tag library.

**Q: Where can I see more TagSpec examples right now?**<br />
A: The most complete catalog currently lives in the [django-language-server](https://github.com/joshuadavidthomas/django-language-server) repository. It’s a little out of date relative to this spec, but it shows the breadth of tags already documented. The plan is to move that catalog into this project once it’s refreshed.

**Q: Isn't this all a bit overboard? A whole specification just for defining template tags?**<br />
A: Look, it's *an* idea for how to do this without utilizing a Django runtime, I never said it was a *good* idea. If you’ve got a better one, I’m all ears.

**Q: Is this an official Django project?**<br />
A: No, it's a community specification for tooling interoperability.

**Q: Can you use this for defining tags from template engines similar to Django, like Jinja2 or Nunjucks?**<br />
A: Potentially! The specification has an `engine` field baked in and the syntax amongst all the "curly" template engines are all similar enough it should be able to. Though it's early enough this has not been tested at all.

**Q: How is this different from Django's template documentation?**<br />
A: TagSpec is machine-readable metadata, not narrative documentation.

## Examples

### Documenting Django's `{% for %}` tag

To show how TagSpecs lines up with real templates, here’s Django’s built-in `{% for %}` tag using its full syntax:

```django
{% for item in items reversed %}
    {{ item }}
{% empty %}
    <p>No items available.</p>
{% endfor %}
```

First, here’s the bare-bones TagSpec equivalent:

```toml
[[libraries.tags]]
name = "for"
type = "block"

[[libraries.tags.args]]
name = "item"
kind = "variable"
required = true

[[libraries.tags.args]]
name = "in"
kind = "syntax"
required = true

[[libraries.tags.args]]
name = "items"
kind = "variable"
required = true

[[libraries.tags.args]]
name = "reversed"
kind = "modifier"
required = false

[[libraries.tags.intermediates]]
name = "empty"
max = 1
position = "last"

[libraries.tags.end]
name = "endfor"
```

This minimal document tells tools everything they need: `for` is a block tag (not standalone), it yields a loop variable called `item`, requires the syntactic keyword `in`, accepts a sequence called `items`, optionally honors a `reversed` modifier, allows a single `empty` branch that must appear last, and closes with `endfor`.

Now here’s the same definition with a few optional hints sprinkled in:

```toml
[[libraries.tags]]
name = "for"
type = "block"
extra = { docs = "https://docs.djangoproject.com/en/stable/ref/templates/builtins/#for" }

[[libraries.tags.args]]
name = "item"
kind = "variable"
required = true
extra = { hint = "loop_variable" }

[[libraries.tags.args]]
name = "in"
kind = "syntax"
required = true

[[libraries.tags.args]]
name = "items"
kind = "variable"
required = true
extra = { hint = "iterable" }

[[libraries.tags.args]]
name = "reversed"
kind = "modifier"
required = false
extra = { affects = "iteration", default = false }

[[libraries.tags.intermediates]]
name = "empty"
max = 1
position = "last"
extra = { label = "empty_branch" }

[libraries.tags.end]
name = "endfor"
extra = { matches = { part = "tag", argument = "item" } }
```

Because every object in the spec exposes an `extra` field, producers can attach documentation links, hints, defaults, or cross-references that downstream tooling may surface to users.

### Documenting your own tag library

Let’s pretend you’ve written a custom `card` block tag that takes a required `title` argument and wraps content:

```django
{% load custom %}

{% card title="Welcome" %}
  <p>Hello, world!</p>
{% endcard %}
```

The minimal TagSpec representation looks like this:

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
type = "keyword"
required = true

[libraries.tags.end]
name = "endcard"
```

This tells tools to load tags from `myapp.templatetags.custom`, expect a block tag named `card`, require a keyword `title` argument, and look for a closing `endcard`.

And here’s an expanded version that shows how `extra` fields can add richer context:

```toml
version = "0.1.0"
engine = "django"

[[libraries]]
module = "myapp.templatetags.custom"
extra = { docs_url = "https://example.com/cards" }

[[libraries.tags]]
name = "card"
type = "block"
extra = { component = "card" }

[[libraries.tags.args]]
name = "title"
kind = "literal"
type = "keyword"
required = true
extra = { hint = "card_heading" }

[libraries.tags.end]
name = "endcard"
extra = { matches = { part = "tag", argument = "title" } }
```

Here the optional `extra` payloads add documentation links, component metadata, argument hints, and a rule that the end tag must repeat the opening tag’s `title`. None of that is required by the spec, but sharing it gives tools richer context to work with.

## Specification & Schema

Read the full specification here: [spec/SPECIFICATION.md](spec/SPECIFICATION.md). It defines:

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
- Document validation via Pydantic

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

The models apply defaults and validate the structure of TagSpec documents.

## License

djtagspecs is licensed under the Apache License, Version 2.0. See the [`LICENSE`](LICENSE) file for more information.

---

djtagspecs is not associated with the Django Software Foundation.

Django is a registered trademark of the Django Software Foundation.
