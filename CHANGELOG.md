# Changelog

All notable changes to this project will be documented in this file.

## [0.1.5] - 2026-03-27

### Added

- Regression tests for additional TypeScript and Go parser edge cases

### Changed

- Improved parser reliability for complex TypeScript signatures
- Improved Go parameter extraction so blank identifier `_` is not treated as a tracked argument

## [0.1.4] - 2026-03-20

### Added

- **Anchor validation**: `code_id` in Markdown anchors must exist in parsed code; unknown references fail the check (exit 1) and appear under **Unknown code_id references** / JSON `unknown_anchors`
- **Code locations in reports**: outdated-doc text report includes `Code: path:line` (relative to project root); JSON `code_changes` includes `code_file` and `code_line`; hint when symbol was removed from codebase

### Changed

- README and spec updated for validation and code locations

## [0.1.3] - 2026-03-15

### Added

- **Go support**: parse `.go` files (functions and methods)
  - Code ID format: `package:FunctionName` or `package:(*Type).Method` or `package:Type.Method`
  - Exclude `vendor`, `*_test.go`
- **TypeScript improvements**: interfaces, type aliases, destructuring in params
- Example `examples/go_sample/` with Go code
- Tests for Go parser

### Changed

- CLI now parses Python, TypeScript/JavaScript, and Go automatically
- README and spec updated with Go format

## [0.1.2] - 2026-03-08

### Added

- **TypeScript/JavaScript support**: parse `.ts`, `.tsx`, `.js`, `.jsx` files
  - Functions, arrow functions, classes, methods
  - `export default function` and `export default class`
  - Code ID format: `path.to.file:name` or `path.to.file:Class.method`
- Exclude `*.d.ts`, `*.test.*`, `*.spec.*`, `node_modules`, `dist`, `build` from parsing
- Example `examples/ts_sample/` with TypeScript code
- Tests for TypeScript parser

### Changed

- CLI now parses both Python and TypeScript/JavaScript automatically
- README updated with Supported Languages section and TypeScript examples
- pyproject.toml: license to SPDX format, keywords for typescript/javascript

## [0.1.1] - 2026-03-01

### Added

- Python parser (functions, class methods)
- Doc parser (Markdown anchors `<!-- livedoc: code_id = "..." -->`)
- Link graph and change detection
- CLI: `python -m livedoc [path] --docs docs --update --ignore PATTERN --format json`
- Config: `.livedoc.json`, `.livedocignore`
- Pre-commit hook support
