# Changelog

All notable changes to this project will be documented in this file.

## [0.1.3] - 2025-02-09

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

## [0.1.2] - 2025-02-09

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

## [0.1.1] - 2024

### Added

- Python parser (functions, class methods)
- Doc parser (Markdown anchors `<!-- livedoc: code_id = "..." -->`)
- Link graph and change detection
- CLI: `python -m livedoc [path] --docs docs --update --ignore PATTERN --format json`
- Config: `.livedoc.json`, `.livedocignore`
- Pre-commit hook support
