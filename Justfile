set dotenv-load := true
set unstable := true

# List all available commands
[private]
default:
    @just --list --list-submodules

bootstrap:
    uv sync

bumpver *ARGS:
    uvx bumpver {{ ARGS }}

generate-schema:
    djts generate-schema -o spec/schema.json

# run pre-commit on all files
lint:
    @just --fmt
    uvx --with pre-commit-uv pre-commit run --all-files
