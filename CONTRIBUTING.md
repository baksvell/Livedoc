# Contributing to LiveDoc

Thanks for your interest in improving LiveDoc.

## Development setup

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install project and dev dependencies:

```bash
pip install -e ".[dev]"
```

## Running checks

- Run tests:

```bash
python -m pytest tests -q
```

- Run livedoc against examples:

```bash
python -m livedoc examples
```

## Coding guidelines

- Keep runtime dependencies minimal.
- Add tests for behavior changes or bug fixes.
- Keep README and spec docs aligned with code changes.

## Pull request checklist

- [ ] Tests pass locally.
- [ ] New behavior is covered by tests.
- [ ] Docs are updated if user-facing behavior changed.
- [ ] Changelog is updated for release-relevant changes.

## Commit message style

Use short, descriptive messages. Examples:

- `feat: add quiet mode to CLI`
- `fix: handle unknown anchors in JSON report`
- `docs: add CI workflow example`
