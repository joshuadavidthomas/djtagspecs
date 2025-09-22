# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project attempts to adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!--
## [${version}]
### Added - for new features
### Changed - for changes in existing functionality
### Deprecated - for soon-to-be removed features
### Removed - for now removed features
### Fixed - for any bug fixes
### Security - in case of vulnerabilities
[${version}]: https://github.com/joshuadavidthomas/djtagspecs/releases/tag/v${version}
-->

## [Unreleased]

### Added

- Support for resolving TagSpec manifests distributed inside Python packages via `pkg://` URIs.

### Changed

- Discovery guidance now prioritises tool-selected manifests and treats packaged catalogs as part of the default lookup flow, relaxing the requirement for root-level `djtagspecs.toml` files.

## [0.2.0]

### Added

- Catalog loader utilities with CLI commands for validation and flattening TagSpec documents.

### Changed

- The `version` field in TagSpec documents is now optional; when omitted, loaders default to the package’s current release.

## [0.1.0]

### Added

- Initial publication of the TagSpecs specification and reference JSON Schema.
- `djts` CLI for generating the schema from the Pydantic models.
- Pydantic models that codify the TagSpecs data model for validation and tooling.

[unreleased]: https://github.com/joshuadavidthomas/djtagspecs/compare/v0.2.0...HEAD
[0.1.0]: https://github.com/joshuadavidthomas/djtagspecs/releases/tag/v0.1.0
[0.2.0]: https://github.com/joshuadavidthomas/djtagspecs/releases/tag/v0.2.0
