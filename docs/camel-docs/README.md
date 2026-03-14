# CAMEL Docs Snapshot for OASIS Dashboard

This directory is a trimmed local snapshot of the upstream CAMEL documentation,
kept only to support OASIS Dashboard development.

## What is intentionally kept

- `get_started/`: local setup guidance for CAMEL
- `key_modules/`: conceptual docs for the main CAMEL building blocks
- `reference/` and `camel*.rst`: API-oriented reference pages
- `index.rst`, `modules.rst`, `conf.py`, `Makefile`: minimal Sphinx entrypoints

## What was intentionally removed

The full upstream `docs/` tree contains a large amount of website-specific and
example-heavy content that is not required in this repository:

- `mintlify/`: generated/website-oriented Mintlify content
- `cookbooks/`: large notebook collection, the main source of repo bloat
- `images/`: large static assets used by the removed website/cookbook content
- `mcp/`: product/site docs outside the scope of OASIS Dashboard usage

If you need the complete documentation, use the upstream CAMEL repositories and
sites instead of re-vendoring the entire docs tree here.

## Updating this snapshot

When refreshing these docs from upstream, keep the snapshot small:

1. Import only the source files that are directly useful for local development.
2. Do not commit generated site content, notebook-heavy cookbooks, or bulk
   image assets unless this repository explicitly depends on them.
3. Record the upstream source or commit in the PR description.

## Optional local build

If you want to render the retained Sphinx sources locally:

```bash
pip install sphinx sphinx_book_theme sphinx-autobuild myst_parser nbsphinx
cd docs/camel-docs
sphinx-autobuild . _build/html --port 8000
```
