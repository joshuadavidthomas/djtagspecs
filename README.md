# djtagspecs

A specification for describing Django template tag syntax.

## Overview

TagSpec is a machine-readable format for describing Django template tag syntax.

If you're familiar with OpenAPI for REST APIs, the TagSpec specification plays a comparable role for Django templates: it captures the structure of tags so tools can reason about them without importing Django or executing any code.

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

If you build tools around Django templates, TagSpecs give your tool a shared contract it can consume to better understand templates without baking parsing rules into your codebase.

Still confused? Skip to the [examples](#examples) to see what a TagSpec document looks like in practice.

## Motivation

I stumbled into the rules and config that lead to the TagSpec specification while working on [django-language-server](https://github.com/joshuadavidthomas/django-language-server). The goal was to surface diagnostics statically without importing Django or executing user code.

The first approach was straightforward but brittle, hard-coding the behavior of Django’s built-in tags. That plan fell apart once I thought about third-party libraries and custom tags. There’s no limit to how many exist in the wild, and baking the rules into a language server both doesn’t scale *and* filled me with a sense of dread at the sheer amount of work it would take.

See, the template engine is hands-off when it comes to template tags. You can pretty much do whatever you want inside one as long as you return a string when it renders. That flexibility is great for authors but makes developing AST-style heuristics almost impossible (if you have any ideas on how to do so, please let me know!). Even the name of an end tag is just convention, Django doesn’t enforce `end<tag_name>`.

But if you step back and think about the pieces you actually need to validate usage, the list is surprisingly small: the tag’s name, the arguments it accepts, whether it requires a closing tag, and which intermediate tags are allowed before that closing tag.

Once that clicked, the only hard part of the work was writing the rules down. Capture the syntax, block structure, and semantics in a structured document and the language server can reuse it. That bit turned into the specification contained in this repository: a declarative format that stores the knowledge instead of the code that interprets it.

Django’s backwards-compatibility story and deprecation policy keep tag APIs pretty stable, so the heavy lift only has to happen once. After that, tooling can stay in sync simply by reading the TagSpec config that tag authors share, whether that’s a third-party library or your own project. The goal is that future tooling can opt into the same definitions without each of us redoing the groundwork.

Publishing the specification outside the language server keeps those rules from being an internal detail. The end goal is library authors can ship their own TagSpec documents, tooling authors can use shared catalogs instead of each crafting bespoke parsing logic, and Django developers get richer tooling when developing their applications.

## Real-World Usage

TagSpecs was created for and powers [django-language-server's](https://github.com/joshuadavidthomas/django-language-server) diagnostics. The language server reads TagSpec documents to understand available tags, then uses that knowledge to analyze templates without importing user code or executing Django.

## FAQ

**Q: I'm still confused, how exactly do I use this library?**<br />
A: Well, you don't exactly. The specification describes a set of rules for statically defining Django template tags so that tools can parse and validate them. This repository contains that specification and a minimal Python library with the reference specification as Pydantic models.

**Q: So… I don't install anything? What exactly *is* this then?**<br />
A: It’s basically the idea I had for describing Django template tags, the rules and config I wrote to parse them, formalized in prose (with a matching set of Pydantic models). By writing it down, my hope is it gives other tooling a shared spec to build against, instead of just living quietly inside [django-language-server](https://github.com/joshuadavidthomas/django-language-server).

**Q: Isn't this all a bit overboard? A whole separate specification and config just for defining template tags?**<br />
A: Look, it's *an* idea for how to do this without utilizing a Django runtime, I never said it was a *good* idea.

**Q: You're telling me I have to define my tags as config in addition to the actual code?**<br />
A: You don't have to do anything you don't want. TagSpecs are purely additive and entirely optional. Yes, it’s extra work on top of writing the tag code, but the goal is to keep it minimal, and the payoff is richer tooling support. Longer term I’d like to explore moving the definition closer to the tag itself (via decorators perhaps?), similar to how DRF leans on OpenAPI decorators to enrich its API descriptions straight from the code.

**Q: Does this parse my Django templates?**<br />
A: No. It describes tag syntax so other tools can parse templates.

**Q: Do I need this for my Django project?**<br />
A: Only if you're building tools or documenting a tag library.

**Q: Where can I see more TagSpec examples right now?**<br />
A: The most complete (and only) catalog currently lives in the [django-language-server](https://github.com/joshuadavidthomas/django-language-server) repository. It’s a little out of date relative to this spec, but it shows the breadth of tags already documented. The plan is to move that catalog into this project ASAP.

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

Here’s how that tag is defined in TagSpecs:

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

This document covers what a tool needs to know: `for` is a block tag (not standalone), it yields a loop variable called `item`, requires the syntactic keyword `in`, accepts a sequence called `items`, optionally honors a `reversed` modifier, allows a single `empty` branch that must appear last, and closes with `endfor`.

If you want to ship extra hints (think documentation links, analyzer defaults, UI labels, etc.) you can hang them off the `extra` field that every object exposes. Here’s the same TagSpec with a few illustrative extras:

```toml
[[libraries.tags]]
name = "for"
type = "block"
extra = { docs = "https://docs.djangoproject.com/en/stable/ref/templates/builtins/#for" }

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
extra = { hint = "iterable_of:item" }

[[libraries.tags.args]]
name = "reversed"
kind = "modifier"
required = false
extra = { affects = "iteration_direction" }

[[libraries.tags.intermediates]]
name = "empty"
max = 1
position = "last"

[libraries.tags.end]
name = "endfor"
```

Those `extra` values are optional metadata that tooling can surface (or ignore) to provide richer feedback. For example, a tool could link out to docs, flag that `items` is an iterable of `item`, or show that `reversed` flips iteration order.

### Documenting your own tag library

Let’s pretend you’ve written a custom `card` block tag that takes a required `title` argument and wraps content:

```django
{% load custom %}

{% card title="Welcome" %}
  <p>Hello, world!</p>
{% endcard %}
```

Here’s how the TagSpec captures that custom tag:

```toml
version = "0.6.0"
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

This version captures the basics: load tags from `myapp.templatetags.custom`, expect a block tag named `card`, require a keyword `title` argument, and look for a closing `endcard`.

## Specification & Schema

Read the full specification here: [spec/SPECIFICATION.md](spec/SPECIFICATION.md). It defines:

- Document structure and fields
- Tag types (block, loader, standalone)
- Argument kinds and semantics
- Validation rules
- Extensibility mechanisms

The repository publishes both the normative specification and a machine-readable schema so producers and tooling vendors stay aligned.

## Reference Implementation

The `djtagspecs` Python package bundles the models, CLI, and helper APIs described below.

### Requirements

- Python 3.10, 3.11, 3.12, 3.13

### Installation

Install from PyPI:

```bash
python -m pip install djtagspecs

# or with uv
uv add djtagspecs
uv sync
```

### CLI Usage

Generate JSON Schema for validation:

```bash
djts generate-schema -o schema.json
```

Omit `-o` to print the schema to stdout. The command guarantees the emitted schema matches the Pydantic models shipped in this distribution.

Validate a catalog (resolves `extends` by default):

```bash
djts validate catalogs/djtagspecs.toml
```

Flatten a catalog into a single document:

```bash
djts flatten catalogs/djtagspecs.toml -o combined.toml
```

List installed Django template tags:

```bash
djts list-tags
```

This introspects your Django project to discover all available template tags. Useful options:

- `--format json|csv|table` - Output format (default: table)
- `--group-by module|package` - Group tags by full module path or top-level package
- `--catalog path/to/catalog.toml` - Show TagSpec coverage statistics
- `--status all|missing|documented` - Filter by TagSpec coverage (requires `--catalog`)
- `--module`, `--library`, `--name` - Filter by pattern

Examples:

```bash
# View all Django built-in tags
djts list-tags --module django

# Export to JSON grouped by package
djts list-tags --format json --group-by package

# Check TagSpec coverage for a specific library
djts list-tags --catalog djtagspecs.toml --status missing

# Get CSV of all i18n tags
djts list-tags --format csv --library i18n
```

### Packaged Catalogs

Libraries may ship TagSpec manifests inside their Python distributions. These documents can be referenced with a `pkg://` URI, which resolves data bundled alongside a module via `importlib.resources`:

```toml
extends = ["pkg://my_library/tag_specs/django.toml"]
```

This lets tools depend on a catalog without copying it into a project checkout.

### Python API

High-level helpers make it straightforward to read and write catalogs:

```python
from pathlib import Path
from djtagspecs import dump_tag_spec, load_tag_spec

catalog_path = Path("catalogs/djtagspecs.toml")
catalog = load_tag_spec(catalog_path)

# ... mutate catalog as needed ...

catalog_path.write_text(dump_tag_spec(catalog), encoding="utf-8")
```

The underlying Pydantic models remain available via `djtagspecs.models` when you need direct access to the data structures.

## License

djtagspecs is licensed under the Apache License, Version 2.0. See the [`LICENSE`](LICENSE) file for more information.

---

djtagspecs is not associated with the Django Software Foundation.

Django is a registered trademark of the Django Software Foundation.
