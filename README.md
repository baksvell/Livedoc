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
2. **Repository structure and stack** — one language for MVP (Python), shared architecture for future languages and IDE support.
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

- **Code parser**: extracts signatures (name, arguments, types) and unique identifiers (e.g., `module.function` or `file:line`).
- **Doc parser**: parses Markdown with explicit anchors (see `spec/code-doc-mapping.md`), associating paragraphs/blocks with `code_id`.
- **Link graph**: stores (code_id, doc_fragment_id) pairs. When code changes (new signature/hash), related fragments are marked as "possibly outdated."
- **Change detector**: compares current code state (signatures/hashes) with the last saved state.

Extensibility: code and doc parsers are per-language plugins; the graph and report are shared.

## Documentation Format

- **Primary format**: Markdown in the repository (e.g., a `docs/` folder or next to modules).
- **Linking to code**: anchors in Markdown (see `spec/code-doc-mapping.md`), optionally plus annotations in code (docstring tags) that reference a fragment id.
- **Site**: generate a static site (MkDocs, Docusaurus, or custom) from the same Markdown files; navigation and search on top of the generated site.

## MVP (First Iteration)

- **Language**: Python
- **Features**:
  - Parse modules (functions, methods, signatures)
  - One documentation page with anchors to those entities
  - Check: when a signature changes in code, the related doc paragraph is marked as outdated
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
├── examples/                # sample project for testing MVP
│   ├── sample_module/
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

3. **First run** (saves code signatures):
   ```bash
   python -m livedoc --docs docs
   ```

4. **CI**: Add to your workflow:
   ```yaml
   - run: pip install living-doc && python -m livedoc --docs docs
   ```

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
python -m livedoc examples --docs docs

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

## CI (GitHub Actions)

The workflow `.github/workflows/livedoc.yml` runs `livedoc check` on push and pull requests. The `examples/.livedoc` folder with signatures is committed so CI has a baseline. If code changes without updating docs or without `--update`, the job fails.

## Publishing to PyPI

```bash
pip install build twine
python -m build
python -m twine upload dist/*
```

Requires a PyPI account and token. Use `__token__` as username and your API token as password.

## Next Steps

- Add parsers for other languages in `parsers/`
- IDE integration: LSP or extension (show docs on hover)
- Generate and serve a documentation site with "outdated" highlights
