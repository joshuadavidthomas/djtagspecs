# TagSpecs

<dl>
    <dt>Version:</dt><dd><code>0.3.0</code></dd>
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
  - [Block Tag](#block-tag-1)
    - [`block`](#block)
    - [`for`](#for)
  - [Loader Tag](#loader-tag-1)
    - [`include`](#include)
  - [Standalone Tag](#standalone-tag-1)
    - [`url`](#url)
- [Reference Schema and Implementation](#reference-schema-and-implementation)
- [Copyright](#copyright)

## Abstract

TagSpecs is a structured description language for Django-style template tags. A TagSpec document captures the static contract that such engines leave to their tag implementations: block layout, expected intermediates, argument signatures, and semantic hints. By externalising this metadata, tooling can reason about templates without importing runtime modules, enabling static inspection, validation, and documentation generation.

## Motivation

Django’s template engine intentionally keeps tag semantics flexible: the core parser produces a flat node list, and each tag implementation interprets its slice of tokens, often acting as a miniature compiler. Conventions exist (for example, end tags starting with `end` plus the name of the beginning tag), but the engine stays deliberately hands-off. Each tag is responsible for parsing its arguments, managing its node list, and negotiating how rendering unfolds. That separation of responsibilities is a powerful extensibility hook, yet it also makes static inspection of tag syntax and semantics uniquely challenging.

That variability makes heuristics brittle at best. Reverse-engineering the intent of even Django’s built-in tags requires bespoke knowledge of each implementation. TagSpecs introduce an explicit, machine-readable contract so tools can recover the structural and semantic information that runtime code currently hides without guesswork.

Consider Django’s built-in `{% block %}` tag. Both of these forms are valid:

```django
{% block content %}
    ...
{% endblock %}

{% block content %}
    ...
{% endblock content %}
```

At a glance this looks trivial and in isolation you could hard-code its parsing rules. But that approach collapses once you account for the rest of Django’s built-ins, let alone the endless third-party or user-defined tags. Even the supposedly simple case of the `block` tag hides engine-specific logic: the moment you step outside Django’s parser you have to reimplement it just to spot a missing `endblock` argument. Inside Django that work lives in `django.template.loader_tags`, which manually splits tokens, tracks previously seen block names, and negotiates the optional name on the closing tag inside `do_block`:

```python
@register.tag("block")
def do_block(parser, token):
    bits = token.contents.split()
    if len(bits) != 2:
        raise TemplateSyntaxError("'%s' tag takes only one argument" % bits[0])
    block_name = bits[1]
    try:
        if block_name in parser.__loaded_blocks:
            raise TemplateSyntaxError(
                "'%s' tag with name '%s' appears more than once" % (bits[0], block_name)
            )
        parser.__loaded_blocks.append(block_name)
    except AttributeError:  
        parser.__loaded_blocks = [block_name]
    nodelist = parser.parse(("endblock",))
    endblock = parser.next_token()
    acceptable_endblocks = ("endblock", "endblock %s" % block_name)
    if endblock.contents not in acceptable_endblocks:
        parser.invalid_block_tag(endblock, "endblock", acceptable_endblocks)
    return BlockNode(block_name, nodelist)
```

`block` is actually one of the simpler built-ins; other tags layer on positional shorthands, optional intermediates, or bespoke validation spread across multiple helpers. From a static tooling perspective, reconstructing those rules means importing Django, executing parser logic, and sidestepping context-sensitive behaviour. A TagSpec captures the same contract declaratively:

```toml
[[libraries]]
module = "django.template.loader_tags"

[[libraries.tags]]
name = "block"
type = "block"

[[libraries.tags.args]]
name = "name"
kind = "literal"

[libraries.tags.end]
name = "endblock"

[[libraries.tags.end.args]]
name = "name"
kind = "literal"
required = false
extra = { matches = { part = "tag", argument = "name" } }
```

With that document in hand, a validator can confirm the lone opening argument, synthesise `endblock` when the closing tag is omitted, and enforce the optional name match—all without touching runtime internals.

Could a tool just import Django and reuse the `do_block` parser? Technically yes, but the runtime API is geared entirely toward rendering: it mutates parser state, instantiates `BlockNode` objects, and enforces syntax by throwing `TemplateSyntaxError` (and related runtime exceptions such as `VariableDoesNotExist`) as side effects while compiling the template. Static tooling would need to execute Django’s parser, evaluate user-defined tag modules, and reverse-engineer  details from AST objects that were never designed to expose them.

Those limitations surfaced while building [django-language-server](https://github.com/joshuadavidthomas/django-language-server). Without a declarative contract to lean on, the project had to choose between running the entire parser or leaving authors blind to those errors. TagSpecs provide the missing middle ground: capture the rules once, share them across projects, surface diagnostics before the template ever hits the engine, and let any editor, linter, or CI pipeline consume that knowledge without firing up Django at all.

Publishing the specification separately ensures the format is not tied solely to that project: other editors, linters, documentation workflows, or bespoke tools can reuse it, and broader community feedback can evolve the vocabulary over time. The hope is that a shared schema makes it easier for others to build their own analysis tooling without reinventing this foundation.

Externalising the rules into configuration pays off in a few ways. Tooling no longer needs to embed bespoke knowledge of each tag implementation; a single catalogue can travel with a library or be distributed independently; and custom tag authors can describe their surface area without patching the tools themselves. TagSpecs is intended to be the interchange format for those shared catalogues.

By describing a tag’s arguments, block structure, and semantics declaratively, TagSpecs supply just enough metadata for a language server (or any static tool) to validate usage, offer completions, and highlight errors without relying on runtime behaviour.

## Rationale

The specification favors a declarative contract because attempts to reconstruct tag rules from runtime ASTs or ad-hoc heuristics are brittle and, quite frankly, headache-inducing. Describing tags explicitly lets tools skip complex parsing and rely on stable metadata instead.

Keeping the rules in configuration also makes them inherently shareable. Multiple tools can point at the same catalogue, and custom libraries can publish their own definitions without asking downstream tooling to ship code patches. The schema aims to be a neutral interchange format rather than a prescriptive implementation detail.

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
- **Tag argument**: a syntactic element that appears in a tag part (opening, intermediate, or closing) and is described by its `kind`.
    - **Argument kind**: the enumerated classification of a tag argument that defines its syntactic role and constraints (for example `any`, `assignment`, or `syntax`).
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

- `version` — optional string identifying the TagSpecs specification version implemented by this document (for example `"0.1.0"`). When omitted, consumers MUST assume the latest published specification version and MAY reject documents that advertise a version they do not understand.
- `engine` — optional string identifier for the template dialect (for example `"django"`, `"jinja2"`). When omitted, consumers MUST treat the engine as `"django"`. This edition of the specification defines behaviour only for the Django dialect; non-Django engines SHOULD supply additional documentation clarifying any divergent semantics.
- `requires_engine` — optional string constraining engine versions for the entire catalog (PEP 440 for Django). When omitted, the catalog is assumed to work with all versions recognised by the declared engine. Any child object that omits its own `requires_engine` inherits this value.
- `extends` — optional array of string references to additional TagSpec documents that this catalog builds upon.
    - Entries are processed left to right before applying the current document.
    - Each entry MAY reference a relative or absolute file path, directory, glob pattern, or URI (for example `pkg://`).
    - Directory and glob handling follow the rules in [Discovery and Composition](#discovery-and-composition), including lexicographic expansion and implementation-defined filename support.
- `libraries` — array of TagLibrary objects. Producers SHOULD include the member even when no libraries are declared. Consumers MUST normalise a missing value to an empty array, and library modules MUST remain unique within a document.
- `extra` — optional object for catalog-level metadata not otherwise covered by this specification (for example documentation URLs, provenance, or tool-specific flags).

Unrecognised top-level members MAY appear. Consumers SHOULD ignore them while preserving their structure when re-serialising the document.

### Tag Library Object

Each entry in `libraries` groups one or more tags exposed by a given importable module.

- `module` — required dotted Python import path that contributes tags (for example `"django.template.defaulttags"`).
- `requires_engine` — optional string overriding the catalog-level constraint for this module. If absent, consumers SHOULD apply the catalog’s `requires_engine` value (if any).
- `tags` — required array of Tag objects. The array itself may be empty, but tag names MUST be unique within the `{engine, library.module, tag.name}` tuple.
- `extra` — optional object reserved for implementation-specific metadata (for example documentation handles or analysis hints). Consumers MUST ignore unknown members inside `extra`.

### Tag Object

Each entry in `libraries.tags` describes a single template tag exposed by the engine and maps to the `Tag` structure in the reference schema.

- `name` — the canonical name of the tag as used in templates.
- `type` — enumerated string describing the structural category of the tag: `"block"`, `"loader"`, or `"standalone"`. This maps to `TagType`.
- `args` — array of `TagArg` objects describing the arguments accepted by the opening tag. The order of the array reflects syntactic order. Defaults to an empty array. When omitted or empty, consumers MUST treat the argument list as permissive: they MUST NOT report missing required arguments or extra supplied arguments at call sites.
- `intermediates` — array of `IntermediateTag` objects describing markers admitted within the tag body. Only meaningful when the tag behaves as a block (for example `type = "block"` or `type = "loader"` with block support). Defaults to an empty array. When omitted or empty, consumers MUST assume no intermediate markers are required.
- `end` — optional `EndTag` object describing the closing tag of a block.
    - `standalone` tags MUST NOT provide `end`.
    - `block` tags MAY omit `end`. If omitted, consumers MUST synthesise the defaults described in [End Tag Defaults](#end-tag-defaults) when absent.
    - `loader` tags without `end` behave as single-node tags. When they supply `end`, they follow the same defaults as block tags.
- `extra` — optional object reserved for implementation-specific metadata (for example documentation handles or analysis hints). Consumers MUST ignore unknown members inside `extra`.

### Tag Types

#### Block Tag

`block` tags enclose a region of the template and optionally admit intermediate markers. They remain valid when the spec omits `end`; consumers MUST synthesise the defaults in [End Tag Defaults](#end-tag-defaults) and accept the tag in minimal form. Examples include `if`, `for`, and `with`.

#### Loader Tag

`loader` tags execute at runtime to load additional templates or components.

They default to single-node behaviour when the spec omits `end` (for example `include`). When the runtime implementation accepts block syntax, the spec MAY provide `end` and `intermediates`, at which point they behave identically to `block` tags for validation purposes (for example third-party component tags that wrap an external template).

#### Standalone Tag

`standalone` tags occupy a single template node and have no matching end tag. They MUST NOT specify `end` or `intermediates`. Examples include `csrf_token`, `now`, and `url`.

### End Tags

The `EndTag` object describes the closing token for block and block-capable loader tags:

- `name` — string naming the closing tag (for example `"endfor"`).
- `args` — array of `TagArg` objects describing the arguments accepted by the closing tag. Defaults to an empty array and follows the same ordering and semantics as opening-tag arguments.
- `required` — boolean indicating whether the closing tag must appear explicitly. Defaults to `true`. When `false`, the closing token is optional and may be implied by template termination or a disallowed token.

#### End Tag Defaults

For `type = "block"` tags:

- When `end` is omitted, consumers MUST synthesise an `EndTag` object with:
    - `name = "end" + tag.name`
    - `args = []`
    - `required = true`

An explicitly provided `end` object overrides these defaults. Loader tags adopt the same behaviour once they declare `end`; when they omit it, they remain single-node tags. Standalone tags MUST NOT supply `end`.

### Intermediate Tags

Intermediate markers allow block tags to model multi-part structures such as `if/elif/else`. Each `IntermediateTag` object contains:

- `name` — the literal name of the marker.
- `args` — array of `TagArg` objects accepted by the marker. Defaults to an empty array. Ordering, typing, and kinds follow the same conventions as opening-tag arguments.
- `min` — optional non-negative integer specifying the minimum number of times the marker must appear. When omitted or `null`, there is no lower bound (effectively zero).
- `max` — optional non-negative integer specifying the maximum number of times the marker may appear. When omitted or `null`, there is no upper bound. Consumers MUST reject values less than `min`.
- `position` — optional enumeration describing placement constraints. `"any"` (default) allows the marker anywhere after the opener and before the end tag. `"last"` restricts the marker to the final position before the end tag (for example `else`).
- `extra` — optional object for implementation-specific metadata (for example semantic hints understood by a language server).

### Tag Arguments

Every `TagArg` definition—whether attached to an opening tag, intermediate marker,
or end tag—exposes the following members:

- `name` — identifier for the argument. For keyword-only arguments this corresponds to the literal keyword in the template.
- `required` — boolean indicating whether the argument is mandatory. Defaults to `true`.
- `type` — enumerated string (`TagArgType`) describing how the argument can be supplied. `"both"` (default) means positional or keyword usage is accepted, `"positional"` restricts to positional usage, and `"keyword"` restricts to keyword usage.
- `kind` — enumerated discriminator (`TagArgKind`) that selects the additional constraints described below.
- `extra` — optional object for implementation-specific metadata such as analyser hints.

#### Argument name

`TagArg.name` provides a stable identifier for overlays, diagnostics, and metadata. Producers SHOULD keep the names descriptive, but consumers MUST treat them as opaque keys.

Argument names MUST be unique within each argument list (opening tag, a specific intermediate marker, or the end tag) so overlays and merge operations can deterministically reference the intended argument. Producers MAY reuse names across different lists when semantics align (for example `for`/`empty`).

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
- Any tag part → `extra.matches` declaring that this argument must equal another argument in the same tag definition. The value SHOULD be an object with `part` (one of `"tag"`, `"end"`, or `"intermediate"`), `argument` (referencing the argument name), and, when `part = "intermediate"`, a `name` identifying the marker. Tools MAY use this to enforce relationships such as Django’s `{% block name %} ... {% endblock name %}` pairing.

Engines MAY introduce additional keys or values as needed; the names above are guidelines rather than an exhaustive vocabulary.

Consumers MUST ignore unknown keys inside `extra` while preserving them for round-tripping, enabling future extension without breaking existing tooling.

When the predefined hint enums are insufficient, producers MAY convey richer semantics inside the `extra` member. Consumers SHOULD surface such data opportunistically while remaining tolerant of its absence.

### Defaults and Normalization

Consumers MUST interpret omitted members according to these defaults, regardless of the document’s serialization format. Unless a default below states otherwise, omission MUST be treated as permissive and MUST NOT introduce validation failures:

- `version` defaults to the latest published specification (`"0.1.0"`).
- `engine` defaults to `"django"`.
- `extends` defaults to an empty array.
- `libraries` defaults to an empty array.
- `tag.args`, `end.args`, and `intermediate.args` default to empty arrays, signalling that no argument presence or arity checks are enforced until definitions appear. `intermediates` defaults to an empty array, signalling that no intermediate markers are required.
- `end.required` defaults to `true`.
- `block` tags without an explicit `end` are normalised using the defaults in [End Tag Defaults](#end-tag-defaults).
- `arg.required` defaults to `true`; `arg.type` defaults to `"both"`.
- `intermediate.position` defaults to `"any"`; `min` and `max` default to `null` (meaning unspecified).

When producing a serialized form, implementations MAY omit members whose values equal the defaults above.

### Progressive Enhancement

TagSpecs are intended to be adopted incrementally. Authors MAY publish the minimal viable document—a catalog header with empty `libraries`, or a tag definition that only states `name` and `type`. Consumers MUST accept these documents, applying the defaults above so that the resulting spec remains permissive. Additional structure (arguments, intermediates, explicit end tags, metadata) MAY be layered on later via overlays or revised catalogs without breaking existing consumers. Tools SHOULD merge such additions using the identity rules defined below and SHOULD continue honouring permissive defaults where detail is absent.

### Identity and Ordering

Overlay evaluation order is deterministic. Consumers apply documents in the sequence resolved by `extends[0]`, `extends[1]`, … `extends[n]`, with the current document evaluated last.

Library identity is defined by `{engine, library.module}`. Tag identity within a document is defined by the tuple `{engine, library.module, tag.name}`. Documents that overlay one another MUST use these composite keys when merging.

When two documents contribute the same object:

- Scalar fields adopt the last non-null value encountered in overlay order.
- Object fields—including any `extra` member—merge shallowly, with later documents winning on key collision.
- Arrays of named items (`args`, `intermediates`, and `end.args`) merge by `name`. Later documents replace existing entries with the same `name`; unique names append in the order they appear.
- All other arrays (for example `libraries` and `tags`) append new items in document order while preserving the original ordering of earlier items. Consumers MUST NOT reorder array members unless explicitly directed by this specification.

#### Example overlay

Given a base catalog that exports a minimal `hero` block tag:

```toml
# catalogs/base.toml
version = "0.3.0"

[[libraries]]
module = "myapp.templatetags.hero"

[[libraries.tags]]
name = "hero"
type = "block"
```

And an overlay that extends it to spell out arguments and intermediates while reusing the structural defaults from the base document:

```toml
# catalogs/hero-overlay.toml
extends = ["catalogs/base.toml"]

[[libraries]]
module = "myapp.templatetags.hero"

[[libraries.tags]]
name = "hero"

[[libraries.tags.args]]
name = "title"
kind = "literal"
required = true

[[libraries.tags.intermediates]]
name = "else"
position = "last"
```

Loading `catalogs/hero-overlay.toml` first applies the base document, then the overlay. Because both files contribute the same tag identity `{engine="django", module="myapp.templatetags.hero", name="hero"}`, the overlay augments the minimal definition: `hero` remains a block tag, gains the required `title` argument, and receives the `else` intermediate. No other tags are affected, and the base file stays valid for consumers that do not load the overlay.

### Validation

A consumer MUST reject a TagSpec document if any of the following hold:

- A library omits `module`.
- Two libraries declare the same `module` value within a single document.
- A tag omits `name` or `type`.
- A tag provides an explicit `end` object whose `name` is missing or empty.
- `type = "standalone"` yet `end` or `intermediates` are supplied.
- `intermediate.max` is provided and less than `intermediate.min`.
- Multiple tags share the same `{engine, library.module, name}` identity within a document.
- Any of `tag.args`, `intermediate.args`, or `end.args` contain duplicate `name` values within the same argument list.
- Multiple intermediates within the same tag specify `position = "last"`.
- The `extends` chain contains circular references (for example, A extends B, B extends C, C extends A).

Consumers SHOULD surface additional diagnostics when template usage violates the structural constraints spelled out by the spec (for example, too many intermediates, missing required arguments, or illegal modifier placement). The exact reporting format is implementation-defined.

Progressive defaults mean that missing definitions are not themselves violations. In particular, consumers MUST NOT report diagnostics about argument presence or intermediate usage until the corresponding definitions exist in the spec.

### Extensibility and Forward Compatibility

TagSpecs are designed for forward compatibility:

- Unknown object members at any level MUST be preserved during round-tripping.
- Producers MAY introduce vendor-specific metadata on any object. Using the provided `extra` member is RECOMMENDED to minimise clashes, but consumers MUST tolerate additional fields even when they appear elsewhere.
- Any object MAY record provenance using `extra.source` (string path or URI). Consumers MUST preserve this value during round-tripping.
- New `TagArg.kind` values may be introduced in future revisions. Consumers MUST ignore kinds they do not recognise while retaining them.
- Additional metadata keys or values under `extra.*` (including new `hint`, `affects`, or `choices` vocabularies) may appear at any time. Consumers MUST preserve unknown keys and values for round-tripping.
- Additional top-level fields may appear in future versions and MUST NOT cause validation failures.

### Discovery and Composition

Productions may combine multiple TagSpec documents. Consumers SHOULD apply the following discovery order:

1. Inline configuration within `pyproject.toml` under `[tool.djtagspecs]`.
2. Catalog manifests explicitly selected by the calling tool (for example through CLI arguments, editor settings, or environment metadata). Tools MAY surface any serialization format they support.
3. Default manifests at the project root when no explicit selection is provided. Implementations SHOULD look for `djtagspecs.toml` and `.djtagspecs.toml`, but MAY recognise additional filenames or extensions consistent with the serialization formats they support.
4. Installed catalogs packaged with libraries.

When the `extends` array is present, consumers MUST resolve each entry in order before applying the current document. Paths are resolved relative to the current document unless the entry uses an implementation-defined URI scheme (for example `pkg://`). For inline configurations located in `pyproject.toml`, the current document is the directory containing that file.

Directory and glob entries MUST expand to the matching, non-recursive set of manifest files supported by the implementation, sorted lexicographically before being appended to the overlay chain. Implementations SHOULD document which patterns they recognise and SHOULD, at minimum, accept common TagSpec serialisations such as `.toml`, `.json`, `.yaml`, or `.yml`.

Overlay documents SHOULD merge fields by the identity rules in [Identity and Ordering](#identity-and-ordering), with later documents overriding earlier values on key collision.

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

### Conformance

Implementations may claim one or more of the following conformance levels:

- **Reader** — parses TagSpec documents, applies defaults, and enforces the validation rules in [Validation](#validation).
- **Writer** — emits valid TagSpec documents and assures round-trip preservation of unknown members.
- **Validator** — applies TagSpecs to template sources for the declared engine, producing diagnostics for structural violations.
- **Catalog** — bundles TagSpec documents with libraries and exposes discovery metadata.

A conforming implementation is RECOMMENDED to document which levels it satisfies and the range of specification versions it supports.

## Examples

The examples below highlight the minimal declaration for each tag type and show how additional structure can be layered on without breaking early adopters.

### Minimal Block Tag

A block tag can be published with only its name and type. Consumers will synthesise `end<name>` (`endif` in this case) and will not enforce any argument or intermediate structure until it is declared.

```toml
version = "0.3.0"
engine = "django"

[[libraries]]
module = "django.template.defaulttags"

[[libraries.tags]]
name = "if"
type = "block"
```

An overlay can later introduce arguments or intermediates without disrupting existing tooling:

```toml
[[libraries]]
module = "django.template.defaulttags"

[[libraries.tags]]
name = "if"
type = "block"

[[libraries.tags.intermediates]]
name = "else"
position = "last"

[[libraries.tags.args]]
name = "condition"
kind = "any"
```

### Minimal Loader Tag

Loader tags default to single-node behaviour when they omit `end`. This minimal spec accepts any argument list until details are supplied.

```toml
version = "0.3.0"
engine = "django"

[[libraries]]
module = "django.template.loader_tags"

[[libraries.tags]]
name = "include"
type = "loader"
```

To progressively tighten validation without introducing a closing tag, later revisions may add argument definitions while keeping the tag single-node:

```toml
[[libraries]]
module = "django.template.loader_tags"

[[libraries.tags]]
name = "include"
type = "loader"

[[libraries.tags.args]]
name = "template"
kind = "literal"

[[libraries.tags.args]]
name = "with"
kind = "syntax"
required = false

[[libraries.tags.args]]
name = "bindings"
kind = "assignment"
required = false

[[libraries.tags.args]]
name = "only"
kind = "modifier"
required = false
```

### Minimal Standalone Tag

Standalone tags must remain single-node and therefore omit `end` and `intermediates`. With no argument definitions, tooling accepts any argument list until authors provide stricter guidance.

```toml
version = "0.3.0"
engine = "django"

[[libraries]]
module = "django.template.defaulttags"

[[libraries.tags]]
name = "url"
type = "standalone"
```

Additional argument structure can be introduced progressively—for example, to describe the required view name and optional assignments:

```toml
[[libraries]]
module = "django.template.defaulttags"

[[libraries.tags]]
name = "url"
type = "standalone"

[[libraries.tags.args]]
name = "pattern"
kind = "literal"

[[libraries.tags.args]]
name = "as"
kind = "syntax"
required = false
```

## Reference Schema and Implementation

A machine-readable JSON Schema for TagSpecs is published alongside this document at `spec/schema.json`. Producers SHOULD validate documents against this schema before distribution. Consumers SHOULD treat the schema as a companion reference but prefer the prose specification when conflicts arise.

A reference implementation of the data model is provided in `src/djtagspecs/models.py` using Pydantic. 

The canonical runtime consumer lives in the [django-language-server](https://github.com/joshuadavidthomas/django-language-server) project; the models in this repository mirror that implementation and illustrate defaulting behaviour, validation, and normalisation of TagSpec documents.

## Copyright

This document has been placed in the public domain per the Creative Commons CC0 1.0 Universal license (http://creativecommons.org/publicdomain/zero/1.0/deed).
