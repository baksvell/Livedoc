# LiveDoc — Living Documentation for Code

[![Living Documentation Check](https://github.com/baksvell/Livedoc/actions/workflows/livedoc.yml/badge.svg)](https://github.com/baksvell/Livedoc/actions/workflows/livedoc.yml)
[![PyPI](https://img.shields.io/pypi/v/living-doc.svg)](https://pypi.org/project/living-doc/)
[![Python](https://img.shields.io/pypi/pyversions/living-doc.svg)](https://pypi.org/project/living-doc/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

LiveDoc links Markdown documentation to code symbols and warns when the linked code changes.

When a function, method, interface, type alias, or Go symbol changes, LiveDoc identifies the related documentation fragment and marks it as **possibly outdated**. This helps teams keep documentation close to the code and verify documentation freshness in local development, pre-commit hooks, and CI.

## Why LiveDoc?

Documentation often becomes outdated after code changes. Tests can verify behavior, but they usually cannot tell whether a README, guide, or API description still matches the current function signature.

LiveDoc adds an explicit link between a Markdown section and a code symbol:

```markdown
<!-- livedoc: code_id = "mymodule.calc:add" -->
## `add`

Adds two numbers and returns the result.
```

On the first run, LiveDoc stores the current code signatures. On later runs, it compares the current code with the stored baseline and reports documentation connected to changed symbols.

## Features

- Links Markdown sections to code through invisible HTML comment anchors
- Detects signature changes that may make documentation outdated
- Validates that every documented `code_id` exists in the scanned project
- Reports the source file and line of changed symbols
- Initializes new projects with `livedoc init`
- Discovers reusable `code_id` values with `livedoc symbols`
- Detects duplicate `code_id` values
- Supports text and JSON output
- Supports project configuration through `.livedoc.json`
- Supports path exclusions through `.livedocignore` and `--ignore`
- Works locally, in pre-commit hooks, and in CI
- Has no required runtime dependencies

## Supported Languages

- **Python**: functions, async functions, instance methods, class methods, static methods, positional-only and keyword-only parameters, `*args`, `**kwargs`, type annotations, default values, and return annotations
- **TypeScript/JavaScript**: functions, arrow functions, classes, methods, overload implementations, interfaces, and type aliases in `.ts`, `.tsx`, `.js`, and `.jsx` files
- **Go**: functions and methods, including pointer and value receivers

LiveDoc excludes common generated, dependency, build, and test paths by default. Additional paths can be excluded through configuration or command-line options.

## Installation

Install the latest release from PyPI:

```bash
pip install living-doc
```

To pin this release:

```bash
pip install "living-doc==0.2.0"
```

Check the installed version:

```bash
livedoc --version
```

You can also run LiveDoc as a Python module:

```bash
python -m livedoc --version
```

LiveDoc requires Python 3.10 or newer.

## Quick Start

### 1. Initialize LiveDoc

From the project root:

```bash
livedoc init .
```

This creates:

```text
.livedoc.json
docs/
docs/README.md
```

Existing configuration and documentation files are preserved. Use `--force` only when you intentionally want to overwrite the generated `.livedoc.json` and starter `docs/README.md` files.

To use a different documentation directory:

```bash
livedoc init . --docs documentation
```

### 2. Discover reusable `code_id` values

```bash
livedoc symbols .
```

For machine-readable output:

```bash
livedoc symbols . --format json
```

Copy the required `code_id` from the output.

### 3. Link a Markdown section to code

Add a LiveDoc anchor before the section it describes:

```markdown
<!-- livedoc: code_id = "mymodule.calc:add" -->
## `add`

Adds two numbers and returns an integer.
```

### 4. Create the initial signature baseline

```bash
livedoc . --docs docs
```

The first check creates:

```text
.livedoc/code_signatures.json
```

Commit this file to the repository. It is the baseline that future checks compare against.

### 5. Check documentation after code changes

After changing the linked function or method, run:

```bash
livedoc . --docs docs
```

LiveDoc reports the connected documentation section as possibly outdated and shows what changed.

### 6. Update the baseline after reviewing the docs

After intentionally changing the API and updating its documentation:

```bash
livedoc . --docs docs --update
```

Commit the updated `.livedoc/code_signatures.json` together with the code and documentation changes.

## Anchor Format

LiveDoc anchors are HTML comments, so they do not appear in rendered Markdown.

### One symbol

```markdown
<!-- livedoc: code_id = "package.module:function_name" -->
## Function documentation
```

### Multiple symbols

```markdown
<!-- livedoc: code_id = "package.module:func_a", "package.module:func_b" -->
## Related functions
```

An anchor can be written across multiple lines:

```markdown
<!-- livedoc:
     code_id = "package.module:Service.create"
-->
## Creating a service
```

The anchor applies to the following Markdown section.

For the complete mapping specification, see [`spec/code-doc-mapping.md`](spec/code-doc-mapping.md).

## `code_id` Examples

### Python

```text
mymodule.calc:add
mymodule.service:UserService.create
```

Format:

```text
module.path:function_name
module.path:ClassName.method_name
```

### TypeScript and JavaScript

```text
src.utils:add
src.services.user:UserService.create
src.models:User
```

Format:

```text
path.to.file:symbol
path.to.file:ClassName.methodName
```

### Go

```text
calculator:Add
service:(*UserService).Create
service:UserService.Validate
```

Format:

```text
package:FunctionName
package:(*Type).Method
package:Type.Method
```

## Configuration

Create `.livedoc.json` in the project root:

```json
{
  "docs": "docs",
  "ignore": ["build", "generated"],
  "ignore_code_ids": ["generated.client:*"],
  "format": "text"
}
```

Supported keys:

| Key | Type | Description |
|---|---|---|
| `docs` | string | Documentation directory relative to the project root |
| `ignore` | array of strings | Additional ignored path segments or glob patterns |
| `ignore_code_ids` | array of strings | Symbol patterns excluded from validation and freshness checks |
| `format` | `text` or `json` | Default output format |

Command-line options override configuration values where applicable.

## `.livedocignore`

Create `.livedocignore` in the project root to exclude paths, one pattern per line:

```text
# Generated files
build
generated
scripts/vendor
```

Empty lines and lines beginning with `#` are ignored.

## Command-Line Usage

Main commands:

```bash
# Initialize configuration and starter documentation
livedoc init .

# Initialize with a custom documentation directory
livedoc init . --docs documentation

# List discovered symbols and reusable code_id values
livedoc symbols .

# List symbols as JSON
livedoc symbols . --format json

# Scan the current project using docs/
livedoc .

# Use a custom documentation directory
livedoc . --docs documentation

# Add ignored paths
livedoc . --ignore tests --ignore generated

# Produce machine-readable check output
livedoc . --format json

# Reduce non-essential output in CI
livedoc . --quiet

# Accept reviewed code and documentation changes
livedoc . --update
```

## Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Documentation is up to date, or the first baseline was created successfully |
| `1` | Possibly outdated documentation or unknown anchor references were found |
| `2` | Configuration, parsing, filesystem, baseline, or duplicate-symbol error |

## Reports

### Text output

Text reports include:

- the affected documentation fragment
- the Markdown file and approximate line
- the change reason
- the previous and current signatures
- the current code location

Example:

```text
Possibly outdated documentation (code changed):

  * docs/api.md#add
    File: docs/api.md, line ~1
    Section: add
    Reason: param default changed
    [mymodule.calc:add]  add(a: int, b: int) -> int  ->  add(a: int, b: int = 0) -> int
    Code: mymodule/calc.py:4
```

### JSON output

Use:

```bash
livedoc . --format json
```

The JSON report contains:

- `ok`
- `outdated`
- `unknown_anchors`
- signature differences
- parameter-level change details when available
- code file and line information

JSON output is intended for CI integrations and other developer tools.

## GitHub Actions

Before enabling CI:

1. Add LiveDoc anchors to the Markdown files.
2. Run LiveDoc locally once.
3. Commit `.livedoc/code_signatures.json`.

Create `.github/workflows/livedoc.yml`:

```yaml
name: Living documentation

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

permissions:
  contents: read

jobs:
  livedoc:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install LiveDoc
        run: python -m pip install "living-doc==0.2.0"

      - name: Check documentation freshness
        run: livedoc . --docs docs --quiet
```

Replace `docs` if the project uses a different documentation directory. You can also set the directory in `.livedoc.json` and run `livedoc . --quiet`.

## Pre-commit

Add a local hook to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: livedoc
        name: LiveDoc
        entry: python -m livedoc
        language: system
        pass_filenames: false
```

Install the hook:

```bash
pip install pre-commit
pre-commit install
```

Run it manually:

```bash
pre-commit run livedoc --all-files
```

## Using LiveDoc in This Repository

Install the project with development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run the quality checks:

```bash
python -m ruff check .
python -m pytest -q
python -m livedoc examples --docs docs
```

Check the version:

```bash
python -m livedoc --version
```

## Repository Structure

```text
LiveDoc/
├── .github/workflows/       # CI workflows
├── examples/                # Python, TypeScript, and Go examples
├── spec/                    # Code-to-documentation mapping specification
├── src/livedoc/
│   ├── core/                # Link graph and signature comparison
│   ├── parsers/             # Python, TypeScript/JavaScript, Go, and Markdown parsers
│   ├── report/              # Text and JSON report generation
│   ├── cli.py               # Command-line interface
│   └── config.py            # Project configuration loader
├── tests/                   # Automated tests
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
└── pyproject.toml
```

## Development

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the development setup, testing commands, coding guidelines, and pull request checklist.

The main local checks are:

```bash
python -m ruff check .
python -m pytest -q
python -m build
python -m twine check dist/*
```

## Publishing to PyPI

Build and validate the distributions:

```bash
python -m build
python -m twine check dist/*
```

Upload the release:

```bash
python -m twine upload dist/*
```

PyPI token authentication uses `__token__` as the username and the API token as the password.

## Roadmap

Possible future improvements:

- richer pull-request annotations
- additional language parsers
- IDE and LSP integration
- generated documentation views with outdated-section highlighting
- optional automatic documentation update suggestions

## Contributing

Contributions, bug reports, and feature requests are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request.

## License

LiveDoc is distributed under the MIT License. See [`LICENSE`](LICENSE).
