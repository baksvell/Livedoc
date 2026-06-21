# Changelog

All notable changes to this project will be documented in this file.

## [0.1.8] - 2026-06-21

### Added

* Added `livedoc --version` command
* Added support for Python `async def` functions
* Added support for positional-only and keyword-only Python parameters
* Added support for Python `*args` and `**kwargs` parameters
* Added support for multiline LiveDoc Markdown anchors
* Added unique fragment identifiers for repeated Markdown headings
* Added detection of conflicting duplicate `code_id` definitions
* Added regression tests for Python, TypeScript, Markdown, and CLI edge cases
* Added CI checks for Python 3.10, 3.11, 3.12, and 3.13
* Added package build and metadata validation to CI

### Changed

* Signature comparison now tracks parameter types, default values, and parameter order
* Improved handling of instance methods, class methods, and static methods in the Python parser
* Improved TypeScript method extraction and overload handling
* TypeScript function calls and control-flow constructs inside methods are no longer reported as class methods
* CLI errors are now reported as readable messages instead of raw tracebacks
* Package metadata and `livedoc.__version__` now use version `0.1.8`
* Development dependencies now include `build` and `twine`
* Existing baselines created by LiveDoc 0.1.7 or earlier may report signature changes once because parameter order, types, and default values are now included in signature hashes. Review the affected documentation and run `livedoc . --update` after confirming the changes

### Fixed

* Fixed version mismatch between package metadata and `livedoc.__version__`
* Fixed Python parser handling of asynchronous functions
* Fixed Python parser handling of positional-only and keyword-only parameters
* Fixed lost documentation fragments when Markdown contains repeated headings
* Fixed crashes caused by invalid signature baseline files
* Fixed crashes caused by Python syntax errors in scanned files
* Fixed false TypeScript methods created from calls such as `if(...)`, `helper(...)`, and `console.log(...)`

## [0.1.7] - 2026-04-03

### Added

* Config support for `ignore_code_ids` to exclude specific symbols or glob patterns from checks

### Changed

* Reports now include explicit change reasons such as `args changed`, `return type changed`, and `symbol removed`
* README updated with `ignore_code_ids` examples and JSON report examples including `reason`

## [0.1.6] - 2026-04-01

### Added

* End-to-end CLI tests built on a small multi-language fixture project
* Reusable test fixtures for Python, TypeScript, Go, and linked Markdown docs

### Changed

* JSON output is now machine-readable on the first run and is no longer mixed with informational text
* CLI reliability improved through full scan-to-report regression coverage

## [0.1.5] - 2026-03-27

### Added

* Regression tests for additional TypeScript and Go parser edge cases

### Changed

* Improved parser reliability for complex TypeScript signatures
* Improved Go parameter extraction so blank identifier `_` is not treated as a tracked argument

## [0.1.4] - 2026-03-20

### Added

* **Anchor validation**: `code_id` in Markdown anchors must exist in parsed code; unknown references fail the check with exit code `1`
* Unknown references appear under **Unknown code_id references** in text output and in the JSON `unknown_anchors` field
* **Code locations in reports**: outdated-documentation reports include `Code: path:line`
* JSON `code_changes` entries include `code_file` and `code_line`
* Added a hint when a tracked symbol has been removed from the codebase

### Changed

* README and specification updated with anchor validation and code-location information

## [0.1.3] - 2026-03-15

### Added

* **Go support** for functions and methods
* Go code ID formats:

  * `package:FunctionName`
  * `package:(*Type).Method`
  * `package:Type.Method`
* Exclusion of `vendor` directories and `*_test.go` files
* **TypeScript improvements** for interfaces, type aliases, and destructuring in parameters
* Added the `examples/go_sample/` Go example
* Added tests for the Go parser

### Changed

* CLI now parses Python, TypeScript/JavaScript, and Go automatically
* README and specification updated with Go code ID formats

## [0.1.2] - 2026-03-08

### Added

* **TypeScript/JavaScript support** for `.ts`, `.tsx`, `.js`, and `.jsx` files
* Support for functions, arrow functions, classes, and methods
* Support for `export default function` and `export default class`
* TypeScript and JavaScript code ID formats:

  * `path.to.file:symbol`
  * `path.to.file:Class.method`
* Exclusion of `*.d.ts`, `*.test.*`, `*.spec.*`, `node_modules`, `dist`, and `build`
* Added the `examples/ts_sample/` TypeScript example
* Added tests for the TypeScript parser

### Changed

* CLI now parses both Python and TypeScript/JavaScript automatically
* README updated with a Supported Languages section and TypeScript examples
* Updated `pyproject.toml` license metadata to use SPDX format
* Added TypeScript and JavaScript package keywords

## [0.1.1] - 2026-03-01

### Added

* Python parser for functions and class methods
* Markdown documentation parser supporting `<!-- livedoc: code_id = "..." -->` anchors
* Link graph and code-signature change detection
* CLI commands and options:

  * `python -m livedoc [path]`
  * `--docs docs`
  * `--update`
  * `--ignore PATTERN`
  * `--format json`
* Configuration through `.livedoc.json` and `.livedocignore`
* Pre-commit hook support
