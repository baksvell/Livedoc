# Living Documentation

[![Living Documentation Check](https://github.com/baksvell/Livedoc/actions/workflows/livedoc.yml/badge.svg)](https://github.com/baksvell/Livedoc/actions/workflows/livedoc.yml)
[![PyPI](https://img.shields.io/pypi/v/living-doc.svg)](https://pypi.org/project/living-doc/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A tool that links documentation to code so it stays up to date. When function signatures, APIs, or arguments change, the system marks related documentation paragraphs as "possibly outdated" and suggests what to fix.

## Goals

- **Code ↔ doc linking**: explicit mapping between code entities (functions, classes, APIs) and documentation fragments
- **Freshness checking**: after code changes — mark outdated sections and suggest updates
- **Contextual view** (planned): show the relevant doc fragment in the IDE when hovering over a function or method call
- **Docs next to code**: store documentation in the repository and view it as a site with navigation and search

## Where to Start (recommendation)

Recommended order:

1. **Code ↔ documentation mapping format** — without it, you can't unambiguously link a doc paragraph to a code entity. Define this first.
2. **Repository structure and stack** — Python, TypeScript/JavaScript, and Go for MVP, shared architecture for future languages and IDE support.
3. **Prototype on one example** — one module, one doc page, code parser, and a check that "the document is outdated after a code change."

In short: **first the format and structure, then a minimal prototype**.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Code parser    │────▶│  Link graph      │◀────│  Doc parser         │
│  (AST / API)    │     │  (code_id ↔ doc) │     │  (markdown + anchors)│
└────────┬────────┘     └────────┬──────────┘     └─────────────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐     ┌──────────────────┐
│  Change         │     │  Report / site   │
│  detector       │────▶│  "outdated" +    │
│  (diff / hash)  │     │  suggestions     │
└─────────────────┘     └──────────────────┘
```

- **Code parser**: extracts signatures (name, arguments, types) and unique identifiers. Supports **Python**, **TypeScript/JavaScript**, and **Go**.
- **Doc parser**: parses Markdown with explicit anchors (see `spec/code-doc-mapping.md`), associating paragraphs/blocks with `code_id`.
- **Link graph**: stores (code_id, doc_fragment_id) pairs. When code changes (new signature/hash), related fragments are marked as "possibly outdated."
- **Change detector**: compares current code state (signatures/hashes) with the last saved state.

Extensibility: code and doc parsers are per-language plugins; the graph and report are shared.

## Documentation Format

- **Primary format**: Markdown in the repository (e.g., a `docs/` folder or next to modules).
- **Linking to code**: anchors in Markdown (see `spec/code-doc-mapping.md`), optionally plus annotations in code (docstring tags) that reference a fragment id.
- **Site**: generate a static site (MkDocs, Docusaurus, or custom) from the same Markdown files; navigation and search on top of the generated site.

## Supported Languages

- **Python**: functions, class methods (`module.path:name` or `module.path:Class.method`)
- **TypeScript/JavaScript**: functions, arrow functions, classes, methods, interfaces, type aliases (`.ts`, `.tsx`, `.js`, `.jsx`). Supports destructuring params. Excludes `*.d.ts`, `*.test.*`, `*.spec.*`, `node_modules`, `dist`, `build`.
- **Go**: functions and methods (`.go`). Format: `package:FunctionName` or `package:(*Type).Method`. Excludes `vendor`, `*_test.go`.

## MVP (First Iteration)

- **Features**:
  - Parse modules (functions, methods, signatures, and language-specific constructs) for **Python**, **TypeScript/JavaScript**, and **Go**
  - Documentation (e.g. Markdown) with `livedoc` anchors linking to code entities
  - Detect outdated doc sections when linked code signatures change; **anchor validation** (each `code_id` must exist in parsed code); **code locations** in reports (`path:line` to the definition)
- **Extensibility**: abstractions for the code parser and anchor format to support more languages and IDE integration later.

## Repository Structure

```
LiveDoc/
├── README.md                 # this file
├── spec/
│   └── code-doc-mapping.md  # anchor format and code↔doc mapping
├── src/
│   └── livedoc/
│       ├── __init__.py
│       ├── core/            # link graph, change detector
│       ├── parsers/         # Python code parser, doc parser
│       └── report/          # "outdated" report, future site generation
├── tests/
├── examples/                # sample project (Python + TypeScript + Go)
│   ├── sample_module/       # Python
│   ├── ts_sample/           # TypeScript
│   ├── go_sample/           # Go
│   └── docs/
└── pyproject.toml
```

## Quick Start (Add to Your Project)

1. **Install**: `pip install living-doc` (or `pip install -e .` from this repo)

2. **Create docs** in `docs/` with anchors linking to code:
   ```markdown
   <!-- livedoc: code_id = "mymodule.calc:add" -->
   ## add
   Adds two numbers.
   ```
   For TypeScript: `<!-- livedoc: code_id = "src.utils:add" -->` (path.to.file:name or path.to.file:Class.method)

3. **First run** (saves code signatures):
   ```bash
   python -m livedoc --docs docs
   ```

4. **CI**: See [GitHub Actions in your project](#github-actions-in-your-project) for a full workflow you can copy.

5. **Optional**: Add `.livedoc.json` in project root for defaults:
   ```json
   {"docs": "docs", "ignore": ["build"], "format": "text"}
   ```

6. **Optional**: Add `.livedocignore` (one pattern per line) to exclude paths:
   ```
   build
   scripts
   ```

7. **Optional**: Pre-commit hook — add to `.pre-commit-config.yaml`:
   ```yaml
   - repo: local
     hooks:
       - id: livedoc
         name: livedoc
         entry: python -m livedoc
         language: system
         pass_filenames: false
   ```
   Then: `pip install pre-commit && pre-commit install`

## Running the MVP (This Repo)

```bash
# Install (optional, for livedoc command)
pip install -e .

# Check links and freshness for the example (from repo root)
python -m livedoc examples

# First run saves code signatures to examples/.livedoc/code_signatures.json.
# After changing a function/method signature, the next run will show
# related doc fragments as "possibly outdated" with a diff of old vs new signature.
# To update signatures after editing docs: --update

# Pre-commit (this repo): pre-commit install && pre-commit run livedoc

# Options (CLI overrides .livedoc.json):
#   --ignore PATTERN   Exclude paths (can be repeated)
#   --format json      Machine-readable output for CI/scripts
#   .livedoc.json      Config: docs, ignore, format
#   .livedocignore     File with ignore patterns (one per line)
```

## GitHub Actions in your project

Use the published package from [PyPI](https://pypi.org/project/living-doc/) so CI matches what developers install locally.

### Prerequisites

1. Add `livedoc` anchors to your Markdown under the folder you pass as `--docs` (often `docs/`).
2. Run **once locally** from the repository root:  
   `pip install living-doc && python -m livedoc . --docs docs`  
   (adjust `--docs` if your folder differs, or set `"docs": "docs"` in `.livedoc.json` and run `python -m livedoc .`).
3. **Commit** `.livedoc/code_signatures.json` (created on first run). CI compares future commits to this baseline; without it, the first CI run only saves signatures and passes.

### Example workflow

Save as `.github/workflows/livedoc.yml` in **your** repository:

```yaml
name: Living documentation

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  livedoc:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install living-doc
        run: pip install living-doc

      - name: Check doc freshness and anchors
        run: python -m livedoc . --docs docs
```

- Replace `docs` with your docs directory if needed, or rely on `.livedoc.json` (`"docs": "..."`) and use `python -m livedoc .`.
- To **pin** the version: `pip install "living-doc==0.1.4"`.
- For **machine-readable** logs: add `--format json` or set `"format": "json"` in `.livedoc.json` (e.g. to parse in a follow-up step).

### When CI fails

- **Outdated docs**: update the Markdown or run `python -m livedoc . --docs docs --update` after intentional API changes, then commit the updated `.livedoc/code_signatures.json`.
- **Unknown anchors**: fix or remove invalid `code_id` values in Markdown (see [Anchor validation](#anchor-validation)).

## Anchor validation

Every `code_id` in a livedoc anchor must match a symbol parsed from your project (Python, TypeScript/JavaScript, Go). If an anchor points to a missing or mistyped id, the check fails with **Unknown code_id references** (exit code 1). The JSON report includes an `unknown_anchors` array.

## Code locations in reports

When documentation is outdated because a linked symbol changed, the text report includes a **Code:** line with the file path (relative to the project root) and line number of the current definition, e.g. `sample_module/calc.py:6`. JSON entries under `code_changes` include `code_file` and `code_line`. If the symbol was removed from the codebase, the report says `(symbol removed from codebase)` instead.

## CI in this repository

The workflow [`.github/workflows/livedoc.yml`](.github/workflows/livedoc.yml) installs **this repo in editable mode** (`pip install -e .`) and runs `python -m livedoc examples --docs docs` so CI always uses the current source. The committed [`examples/.livedoc/code_signatures.json`](examples/.livedoc/code_signatures.json) is the baseline; if example code changes without updating docs or signatures, the job fails.

## Publishing to PyPI

```bash
pip install build twine
python -m build
python -m twine upload dist/*
```

Requires a PyPI account and token. Use `__token__` as username and your API token as password.

## GitHub About (repository homepage)

On [github.com/baksvell/Livedoc](https://github.com/baksvell/Livedoc), click **⚙️** next to **About** and set:

| Field | Suggested value |
|--------|------------------|
| **Description** | Link docs to code; flag outdated Markdown when signatures change. |
| **Website** | https://pypi.org/project/living-doc/ |
| **Topics** | `documentation`, `living-docs`, `python`, `typescript`, `go`, `golang`, `code-docs`, `markdown`, `developer-tools` |

*(Topics are added one by one in the About editor.)*

## Next Steps

- Add parsers for other languages in `parsers/`
- IDE integration: LSP or extension (show docs on hover)
- Generate and serve a documentation site with "outdated" highlights
