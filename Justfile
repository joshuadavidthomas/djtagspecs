set dotenv-load := true
set unstable := true

# List all available commands
[private]
default:
    @just --list --list-submodules

[private]
nox SESSION *ARGS:
    uv run nox --session "{{ SESSION }}" -- "{{ ARGS }}"

bootstrap:
    uv sync --locked

bumpver *ARGS:
    uvx bumpver {{ ARGS }}

coverage *ARGS:
    @just nox coverage {{ ARGS }}

generate-schema:
    djts generate-schema -o spec/schema.json

lint:
    @just --fmt
    @just nox lint

lock *ARGS:
    uv lock {{ ARGS }}

test *ARGS:
    @just nox test {{ ARGS }}

testall *ARGS:
    @just nox tests {{ ARGS }}

types *ARGS:
    @just nox types {{ ARGS }}
