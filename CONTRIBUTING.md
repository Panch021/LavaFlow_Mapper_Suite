# Contributing to LavaFlow Mapper Suite

Thank you for your interest in improving LavaFlow Mapper Suite! This project is developed at the
Instituto Geofísico – Escuela Politécnica Nacional (IG-EPN, Ecuador) to support volcano
monitoring, and contributions from the volcanology and remote-sensing community are very
welcome.

By participating you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report a bug**: open an issue with the *Bug report* template.
- **Suggest a feature**: open an issue with the *Feature request* template.
- **Share a use case**: tell us where you used the suite (volcano, eruption, publication or
  report). This helps us prioritise and document real applications.
- **Improve the documentation** in `docs/` (Markdown, built with MkDocs).
- **Contribute code or an example project** through a pull request.

## Development setup

```bash
git clone https://github.com/Panch021/LavaFlow_Mapper_Suite.git
cd LavaFlow_Mapper_Suite
# Pixi
pixi run -e test test
# or Conda / pip
conda env create -f environment.yml && conda activate lavaflow_mapper
python -m pip install -e ".[dev]"
```

Run the app with `lavaflow-suite` (or `python lavaflow_mapper_suite.py`).

## Pull-request workflow

1. Open (or comment on) an issue describing the change.
2. Create a branch from `main`: `git switch -c fix/short-description`.
3. Make small, focused commits with clear messages (English, imperative mood, e.g.
   `Fix weekly totals in anomalies summary`).
4. Add or update tests in `tests/` for any change in behaviour. Tests must run offline:
   mock network calls (FIRMS API, tile servers).
5. Check locally:
   ```bash
   python -m pytest
   ruff check lavaflow_suite tests
   mkdocs build --strict      # if you changed the docs
   ```
6. Add a line under **[Unreleased]** in `CHANGELOG.md`.
7. Open a pull request and fill in the template. CI must pass before merging.

## Code guidelines

- Python ≥ 3.10, PEP 8, line length ≤ 110.
- Shared logic belongs in `lavaflow_suite/common.py`. Figures used by both a tab and the
  report must come from a single builder function.
- Each tab module exposes `get_layout()` and `register_callbacks(app)`.
- Never commit personal data or credentials: no FIRMS `map_key`, and no `projects/`
  folder.
- Keep large data out of the repository. Small example projects (< 5 MB) are fine.

## Releases (maintainers)

1. Update `__version__` in `lavaflow_suite/__init__.py` and move the *Unreleased* notes in
   `CHANGELOG.md` under the new version.
2. Commit, then tag: `git tag -a v2.1.0 -m "v2.1.0" && git push --tags`.
3. The *release* workflow creates the GitHub release. Zenodo archives it and mints a DOI.

## Getting help

Ask in an issue labelled *question*. We try to answer within two weeks.
