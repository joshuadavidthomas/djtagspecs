# TagSpecs

<dl>
    <dt>Version:</dt><dd><code>0.1.0</code></dd>
    <dt>Author:</dt><dd>Josh Thomas</dd>
    <dt>Status:</dt><dd>Draft / Pre-1.0</dd>
    <dt>Created:</dt><dd>2025-09-20</dd>
    <dt>Updated:</dt><dd>2025-09-20</dd>
</dl>

This document is the normative definition of the TagSpecs data model for expressing the static interface of Django-style template tags. It prescribes the required objects, fields, and semantics in a serialization-agnostic manner so that specifications can be expressed in TOML, JSON, YAML, or any other structured format.

> The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Table of Contents**
- [Abstract](#abstract)
- [Motivation](#motivation)
- [Rationale](#rationale)
- [Goals](#goals)
    - [Non-goals](#non-goals)
- [Terminology](#terminology)
- [Serialization Formats](#serialization-formats)
- [Versioning](#versioning)
- [Specification](#specification)
    - [TagSpec Document](#tagspec-document)
    - [Tag Library Object](#tag-library-object)
    - [Tag Object](#tag-object)
    - [Tag Types](#tag-types)
        - [Block Tag](#block-tag)
        - [Loader Tag](#loader-tag)
        - [Standalone Tag](#standalone-tag)
    - [End Tags](#end-tags)
    - [Intermediate Tags](#intermediate-tags)
    - [Tag Arguments](#tag-arguments)
        - [Argument name](#argument-name)
        - [Argument ordering and type](#argument-ordering-and-type)
        - [Argument kinds](#argument-kinds)
        - [Extra metadata](#extra-metadata)
    - [Defaults and Normalization](#defaults-and-normalization)
    - [Identity and Ordering](#identity-and-ordering)
- [Validation](#validation)
- [Extensibility and Forward Compatibility](#extensibility-and-forward-compatibility)
- [Discovery and Composition](#discovery-and-composition)
- [Conformance](#conformance)
- [Examples](#examples)
  - [Block Tag: `for`](#block-tag-for)
  - [Loader Tag: `include`](#loader-tag-include)
  - [Standalone Tag: `url`](#standalone-tag-url)
- [Reference Schema and Implementation](#reference-schema-and-implementation)
- [Copyright](#copyright)

## Abstract

TagSpecs is a structured description language for Django-style template tags. A TagSpec document captures the static contract that such engines leave to their tag implementations: block layout, expected intermediates, argument signatures, and semantic hints. By externalising this metadata, tooling can reason about templates without importing runtime modules, enabling static inspection, validation, and documentation generation.

## Motivation

Django’s template engine intentionally keeps tag semantics flexible: the core parser produces a flat node list, and each tag implementation interprets its slice of tokens, often acting as a miniature compiler. Conventions exist (for example, end tags often start with `end`), but the engine stays deliberately hands-off. Each tag is responsible for parsing its arguments, managing its node list, and negotiating how rendering unfolds. That separation of responsibilities is a powerful extensibility hook, yet it also makes static inspection of tag syntax and semantics uniquely challenging.

That variability makes heuristics brittle at best. Reverse-engineering the intent of even Django’s built-in tags requires bespoke knowledge of each implementation. TagSpecs introduce an explicit, machine-readable contract so tools can recover the structural and semantic information that runtime code currently hides without guesswork.

The format was born out of building the [django-language-server](https://github.com/joshuadavidthomas/django-language-server). The goal was to surface template diagnostics statically, without importing user code or executing the Django runtime. Template tags commonly signal misuse by raising `TemplateSyntaxError`, `VariableDoesNotExist`, or other exceptions during rendering—far too late for editor tooling. 

Publishing the specification separately ensures the format is not tied solely to that project: other editors, linters, documentation workflows, or bespoke tools can reuse it, and broader community feedback can evolve the vocabulary over time. The hope is that a shared schema makes it easier for others to build their own analysis tooling without reinventing this foundation.

By describing a tag’s arguments, block structure, and semantics declaratively, TagSpecs supply just enough metadata for a language server (or any static tool) to validate usage, offer completions, and highlight errors without relying on runtime behaviour.

## Rationale

The specification favors a declarative contract because attempts to reconstruct tag rules from runtime ASTs or ad-hoc heuristics are brittle and, quite frankly, headache-inducing. Describing tags explicitly lets tools skip complex parsing and rely on stable metadata instead.

Choosing static configuration introduces the risk of drifting out of sync with the runtime, but each library can annotate compatibility ranges and quirks with `requires_engine` and `extra`, keeping the core schema simple while leaving room for nuance. 

The same trade-off applies to verbosity: encoding complex tag syntax as structured data takes effort, yet the goal is to make that work pay off in reusable, reliable tooling instead of replacing one opaque system with another.

This approach also keeps the core tightly scoped. `extra` exists so producers can attach engine-specific notes without reopening the spec; argument names provide stable identifiers for overlays and diagnostics; and arrays preserve authoring order so positional interpretation and merges stay predictable.

Finally, the JSON Schema published alongside this document is intended as a companion to the prose, making validation easy while leaving the narrative description as the normative reference.

## Goals

TagSpecs is meant to describe the essentials of a tag catalogue: which engine it targets, which modules it pulls from, and how each tag is structured. In practice, the format captures the opening syntax, the block layout (including intermediates and terminators), and the kinds of arguments a tag accepts.

The document is designed as input for static tooling—linters, language servers, or refactoring tools—but it stays deliberately lightweight by keeping the schema declarative and relying on `extra` metadata for engine-specific details.

As the format matures, there is room to model filter expressions and their argument semantics, and to track cross-tag relationships such as inheritance-aware diagnostics. These ideas remain outside the current scope, but the schema leaves space to incorporate them once there is shared experience with the core data model.

### Non-goals

TagSpecs does not attempt to describe runtime behaviour or side effects, nor does it model the full template expression grammar or front-end languages like HTML and CSS. It also is not an executable specification for template engines; the focus stays on static structure and metadata that complement, rather than replace, the runtime implementation.

## Terminology

- **TagSpec document**: a catalogue that describes one or more tag libraries for a template engine.
- **Engine**: the template dialect that defines parsing and evaluation rules (for example `django`, `jinja2`).
- **Tag library**: a group of tag definitions published by a single importable module.
- **Tag**: a engine template directive such as `if`, `for`, or `include`.
    - **Block tag**: a tag that encloses a region and is closed by a matching end tag.
    - **Loader tag**: a tag that fetches or includes other templates and may optionally behave like a block tag.
    - **Standalone tag**: a tag that does not wrap body content and has no end tag.
- **End tag**: the closing directive for a block or block-capable loader tag (for example `endfor`).
- **Intermediate tag**: a marker that can appear between the opener and the end of a block (for example `elif` or `else`).
- **Tag argument**: a syntactic element that appears in the tag declaration and is described by its `kind`.
- **Argument kind**: ...
- **Producer**: the author or repository that maintains a TagSpec document (for example, a library shipping specs, or a team curating project overrides).
- **Consumer**: a tool that reads TagSpec documents (for example, validators, language servers, editors).

## Serialization Formats

The TagSpecs data model is format-neutral. Implementations MAY serialise documents using any deterministic structured format (for example JSON, TOML, or YAML) as long as the resulting document preserves the required structure defined in this specification. 

The JSON Schema published alongside this document serves as an illustrative mapping to JSON and may be adapted to other formats. 

Examples in this document use TOML purely for readability; their semantics do not imply a canonical encoding.

## Versioning

A TagSpec document declares the specification version it implements via the `version` field. The format follows Semantic Versioning. 

Prior to `1.0.0`, breaking changes MAY occur in any `0.x` release and consumers SHOULD pin to an exact version. After `1.0.0`, breaking changes will increment the major version, additive changes will increment the minor version, and corrective edits will increment the patch version.

## Specification

### TagSpec Document

The root document captures catalog-wide metadata and the set of tag libraries it exports. A valid document MUST provide the following members unless a default is explicitly defined below:

- `version` — required string identifying the TagSpecs specification version implemented by this document (for example `"0.1.0"`). Consumers MUST reject documents that advertise a version they do not understand.
- `engine` — optional string identifier for the template dialect (for example `"django"`, `"jinja2"`). When omitted, consumers MUST treat the engine as `"django"`. This edition of the specification defines behaviour only for the Django dialect; non-Django engines SHOULD supply additional documentation clarifying any divergent semantics.
- `requires_engine` — optional string constraining the supported engine versions (for Django, a PEP 440 version specifier). Consumers SHOULD honour this constraint when selecting specs for analysis.
- `extends` — optional array of string references to additional TagSpec documents that this catalog builds upon. Entries are processed in order before applying the current document.
- `libraries` — array of TagLibrary objects. The array itself may be empty, but library modules MUST be unique within a document.
- `extra` — optional object for catalog-level metadata not otherwise covered by this specification (for example documentation URLs, provenance, or tool-specific flags).

Unrecognised top-level members MAY appear. Consumers SHOULD ignore them while preserving their structure when re-serialising the document.

### Tag Library Object

Each entry in `libraries` groups one or more tags exposed by a given importable module.

- `module` — required dotted Python import path that contributes tags (for example `"django.template.defaulttags"`).
- `requires_engine` — optional string constraining the supported engine versions for this module. When omitted, consumers SHOULD fall back to the catalog-level constraint.
- `tags` — required array of Tag objects. The array itself may be empty, but tag names MUST be unique within the `{engine, module}` tuple.
- `extra` — optional object reserved for implementation-specific metadata (for example documentation handles or analysis hints). Consumers MUST ignore unknown members inside `extra`.

### Tag Object

Each entry in `libraries.tags` describes a single template tag exposed by the engine and maps to the `Tag` structure in the reference schema.

- `name` — the canonical name of the tag as used in templates.
- `type` — enumerated string describing the structural category of the tag: `"block"`, `"loader"`, or `"standalone"`. This maps to `TagType`.
- `args` — array of `TagArg` objects describing the arguments accepted by the opening tag. The order of the array reflects syntactic order. Defaults to an empty array.
- `intermediates` — array of `IntermediateTag` objects describing markers admitted within the tag body. Only meaningful when the tag behaves as a block (for example `type = "block"` or `type = "loader"` with block support). Defaults to an empty array.
- `end` — optional `EndTag` object describing the closing tag of a block. 
    - `block` tags MUST define `end`. 
    - `loader` tags MAY define `end` when the tag implementation supports block syntax. 
    - `standalone` tags MUST NOT provide `end`.
- `extra` — optional object reserved for implementation-specific metadata (for example documentation handles or analysis hints). Consumers MUST ignore unknown members inside `extra`.

### Tag Types

#### Block Tag

`block` tags enclose a region of the template and optionally admit intermediate markers. They require a matching end tag and may control context within their body. Examples include `if`, `for`, and `with`.

#### Loader Tag

`loader` tags execute at runtime to load additional templates or components. 

They may behave like standalone tags (for example `include`) or like block tags when the implementation accepts block syntax (for example third-party component tags that wrap an external template). 

Loader tags MAY provide `intermediates` and `end` when the runtime implementation recognises them.

#### Standalone Tag

`standalone` tags occupy a single template node and have no matching end tag. Examples include `csrf_token`, `now`, and `url`.

### End Tags

The `EndTag` object describes the closing token for block and block-capable loader tags:

- `name` — string naming the closing tag (for example `"endfor"`).
- `required` — boolean indicating whether the closing tag must appear explicitly. Defaults to `true`. When `false`, the closing token is optional and may be implied by template termination or a disallowed token.

### Intermediate Tags

Intermediate markers allow block tags to model multi-part structures such as `if/elif/else`. Each `IntermediateTag` object contains:

- `name` — the literal name of the marker.
- `min` — optional non-negative integer specifying the minimum number of times the marker must appear. When omitted or `null`, there is no lower bound (effectively zero).
- `max` — optional non-negative integer specifying the maximum number of times the marker may appear. When omitted or `null`, there is no upper bound. Consumers MUST reject values less than `min`.
- `position` — optional enumeration describing placement constraints. `"any"` (default) allows the marker anywhere after the opener and before the end tag. `"last"` restricts the marker to the final position before the end tag (for example `else`).
- `extra` — optional object for implementation-specific metadata (for example semantic hints understood by a language server).

### Tag Arguments

Every `TagArg` definition exposes the following members:

- `name` — identifier for the argument. For keyword-only arguments this corresponds to the literal keyword in the template.
- `required` — boolean indicating whether the argument is mandatory. Defaults to `true`.
- `type` — enumerated string (`TagArgType`) describing how the argument can be supplied. `"both"` (default) means positional or keyword usage is accepted, `"positional"` restricts to positional usage, and `"keyword"` restricts to keyword usage.
- `kind` — enumerated discriminator (`TagArgKind`) that selects the additional constraints described below.
- `extra` — optional object for implementation-specific metadata such as analyser hints.

#### Argument name

`TagArg.name` provides a stable identifier for overlays, diagnostics, and metadata. Producers SHOULD keep the names descriptive, but consumers MUST treat them as opaque keys.

#### Argument ordering and type

Arguments appear in the order they are written in template syntax. 

`TagArg.type` indicates whether an argument may be positional, keyword, or both. 

Engines that follow Python-style semantics (for example Django) SHOULD keep positional arguments before keyword arguments. Consumers MAY rely on this order when interpreting positional arguments.
#### Argument kinds

The `TagArg.kind` field conveys the syntactic class of the argument value. The following values are defined:

- `any` — value may be any template expression or literal recognised by the engine.
- `assignment` — introduces one or more `name = expression` bindings (for example `{% with user as person %}` or `{% url ... as urlvar %}`). Producers MAY record additional metadata about the binding behaviour inside `extra`.
- `choice` — restricts the argument to a closed set of string literals. Producers SHOULD list the allowed literals under `extra.choices`.
- `literal` — indicates that the argument is a literal token. Producers MAY record semantic meaning for the literal under `extra`.
- `modifier` — represents boolean-style switches that alter behaviour (for example `reversed` on `for`). Producers MAY describe the affected scope under `extra`.
- `syntax` — models mandatory syntactic tokens that have no runtime value (for example the `in` keyword in `{% for x in items %}`).
- `variable` — denotes a template variable or filter expression recognised by the engine.

#### Extra metadata

Tag arguments MAY carry additional semantics using the `extra` object. The following suggestions show how producers can attach additional metadata when it helps downstream tooling:

- `kind = "assignment"` → `extra.hint` describing how bound values behave (examples: `"context_extension"`, `"variable_capture"`, `"parameter_passing"`).
- `kind = "literal"` → `extra.hint` naming what the literal references (examples: `"url_name"`, `"template_path"`, `"block_name"`, `"staticfile"`, `"library_name"`, `"cache_key"`, `"setting_name"`).
- `kind = "choice"` → `extra.choices` listing permitted literal values.
- `kind = "modifier"` → `extra.affects` indicating which evaluation scope changes (examples: `"context"`, `"iteration"`, `"rendering"`, `"inheritance"`).

Engines MAY introduce additional keys or values as needed; the names above are guidelines rather than an exhaustive vocabulary.

Consumers MUST ignore unknown keys inside `extra` while preserving them for round-tripping, enabling future extension without breaking existing tooling.

When the predefined hint enums are insufficient, producers MAY convey richer semantics inside the `extra` member. Consumers SHOULD surface such data opportunistically while remaining tolerant of its absence.

### Defaults and Normalization

Consumers MUST interpret omitted members according to these defaults, regardless of the document’s serialization format:

- `engine` defaults to `"django"`.
- `extends` defaults to an empty array.
- `args` and `intermediates` default to empty arrays.
- `end.required` defaults to `true`.
- `arg.required` defaults to `true`; `arg.type` defaults to `"both"`.
- `intermediate.position` defaults to `"any"`; `min` and `max` default to `null` (meaning unspecified).

When producing a serialized form, implementations MAY omit members whose values equal the defaults above.

### Identity and Ordering

Tag identity within a document is defined by the tuple `{engine, library.module, tag.name}`. Documents that overlay one another MUST use this composite key when merging tags. Arrays preserve authoring order. Consumers MUST NOT reorder `libraries`, `tags`, `args`, or `intermediates` unless explicitly directed by the specification.

## Validation

A consumer MUST reject a TagSpec document if any of the following hold:

- A library omits `module`.
- Two libraries declare the same `module` value within a single document.
- A tag omits `name` or `type`.
- `type = "block"` but `end` is missing or `end.name` is empty.
- `type = "standalone"` yet `end` or `intermediates` are supplied.
- `intermediate.max` is provided and less than `intermediate.min`.
- Multiple tags share the same `{engine, library.module, name}` identity within a document.

Consumers SHOULD surface additional diagnostics when template usage violates the structural constraints spelled out by the spec (for example, too many intermediates, missing required arguments, or illegal modifier placement). The exact reporting format is implementation-defined.

## Extensibility and Forward Compatibility

TagSpecs are designed for forward compatibility:

- Unknown object members at any level MUST be preserved during round-tripping.
- Producers MAY introduce vendor-specific metadata on any object. Using the provided `extra` member is RECOMMENDED to minimise clashes, but consumers MUST tolerate additional fields even when they appear elsewhere.
- New `TagArg.kind` values may be introduced in future revisions. Consumers MUST ignore kinds they do not recognise while retaining them.
- Additional metadata keys or values under `extra.*` (including new `hint`, `affects`, or `choices` vocabularies) may appear at any time. Consumers MUST preserve unknown keys and values for round-tripping.
- Additional top-level fields may appear in future versions and MUST NOT cause validation failures.

## Discovery and Composition

Productions may combine multiple TagSpec documents. Consumers SHOULD apply the following discovery order:

1. Inline configuration within `pyproject.toml` under `[tool.djtagspecs]`.
2. `djtagspecs.toml` at the project root.
3. `.djtagspecs.toml` at the project root.
4. Installed catalogs packaged with libraries.

When the `extends` array is present, consumers MUST resolve each entry in order before applying the current document. Paths are resolved relative to the current document unless the entry uses an implementation-defined URI scheme (for example `pkg://`). Overlay documents SHOULD merge fields by the identity rules in §3.8, with later documents overriding earlier values on key collision.

An inline configuration uses the same structure as standalone files. For example:

```toml
[tool.djtagspecs]
version = "0.1.0"
engine = "django"

[[tool.djtagspecs.libraries]]
module = "myproject.templatetags.blog"

[[tool.djtagspecs.libraries.tags]]
name = "hero"
type = "block"
```

## Conformance

Implementations may claim one or more of the following conformance levels:

- **Reader** — parses TagSpec documents, applies defaults, and enforces the validation rules in §4.
- **Writer** — emits valid TagSpec documents and assures round-trip preservation of unknown members.
- **Validator** — applies TagSpecs to template sources for the declared engine, producing diagnostics for structural violations.
- **Catalog** — bundles TagSpec documents with libraries and exposes discovery metadata.

A conforming implementation is RECOMMENDED to document which levels it satisfies and the range of specification versions it supports.

## Examples

### Block Tag: `for`

```django
{% for item in items %}
    {{ item }}
{% empty %}
    <p>No items available.</p>
{% endfor %}
```

```toml
version = "0.1.0"
engine = "django"

[[libraries]]
module = "django.template.defaulttags"

[[libraries.tags]]
name = "for"
type = "block"

[libraries.tags.end]
name = "endfor"
required = true

[[libraries.tags.intermediates]]
name = "empty"
min = 0
max = 1
position = "last"

[[libraries.tags.args]]
name = "loop_vars"
kind = "any"
required = true

[[libraries.tags.args]]
name = "in"
kind = "syntax"
required = true

[[libraries.tags.args]]
name = "iterable"
kind = "variable"
required = true

[[libraries.tags.args]]
name = "as"
kind = "syntax"
required = false

[[libraries.tags.args]]
name = "context_var"
kind = "assignment"
required = false
hint = "context_extension"
```

### Loader Tag: `include`

```django
{% include "partials/card.html" with product=product only %}
{% include "partials/card.html" with product=product highlight=True %}
```

```toml
version = "0.1.0"
engine = "django"

[[libraries]]
module = "django.template.loader_tags"

[[libraries.tags]]
name = "include"
type = "loader"

[[libraries.tags.args]]
name = "template"
kind = "literal"
hint = "template_path"
required = true

[[libraries.tags.args]]
name = "with"
kind = "syntax"
required = false

[[libraries.tags.args]]
name = "bindings"
kind = "assignment"
required = false
hint = "parameter_passing"

[[libraries.tags.args]]
name = "only"
kind = "modifier"
required = false
affects = "context"
```

### Standalone Tag: `url`

```django
<a href="{% url 'account:detail' user.pk %}">View account</a>

{% url 'blog:index' as index_url %}
<a href="{{ index_url }}">Blog</a>
```

```toml
version = "0.1.0"
engine = "django"

[[libraries]]
module = "django.template.defaulttags"

[[libraries.tags]]
name = "url"
type = "standalone"

[[libraries.tags.args]]
name = "pattern"
kind = "literal"
hint = "url_name"
required = true

[[libraries.tags.args]]
name = "args"
kind = "variable"
required = false

[[libraries.tags.args]]
name = "as"
kind = "syntax"
required = false

[[libraries.tags.args]]
name = "context_var"
kind = "assignment"
required = false
hint = "variable_capture"
```

## Reference Schema and Implementation

A machine-readable JSON Schema for TagSpecs is published alongside this document at `spec/schema.json`. Producers SHOULD validate documents against this schema before distribution. Consumers SHOULD treat the schema as a companion reference but prefer the prose specification when conflicts arise.

A reference implementation of the data model is provided in `src/django_tagspecs/models.py` using Pydantic. 

The canonical runtime consumer lives in the [django-language-server](https://github.com/joshuadavidthomas/django-language-server) project; the models in this repository mirror that implementation and illustrate defaulting behaviour, validation, and normalisation of TagSpec documents.

## Copyright

This document has been placed in the public domain per the Creative Commons CC0 1.0 Universal license (http://creativecommons.org/publicdomain/zero/1.0/deed).
