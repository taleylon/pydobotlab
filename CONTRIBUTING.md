# Contributing

Use Python 3.10 or newer and a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,gui]"
python -m pytest --timeout=30
ruff check .
ruff format --check .
```

Tests use simulated devices; they do not move connected hardware. The GUI
can be exercised without a display with `QT_QPA_PLATFORM=offscreen`.

## Python style

- Use descriptive verbs for functions and descriptive nouns for variables.
  Keep established coordinate names (`x`, `y`, `z`, `r`) and the documented
  DobotLab method signatures so existing scripts remain compatible.
- Prefer direct code to trivial forwarding helpers. Use public methods for
  supported operations and GUI callbacks; reserve leading underscores for
  state and implementation details that require internal synchronization.
- Use `pathlib.Path` for filesystem paths, explicit UTF-8 for text files,
  built-in generic types, and `Type | None` for optional values.
- Keep imports at module scope unless an optional dependency or circular
  dependency requires delaying them. Do not use dynamic `__import__` calls.
- Run Ruff and the hardware-free tests before submitting changes. Add
  regression tests when fixing behavior, especially transport and queue bugs.

## Package boundaries

`protocol.py` encodes frames, `transport.py` owns serial/TCP connections,
`device.py` exposes the robot API, and `discovery.py` finds devices. The
optional `panel` package contains the Qt GUI. Keep Qt imports out of the
base library. `simulator.py` supplies a software serial backend for testing.

## Documentation

Install `python -m pip install -e ".[docs]"`, then use `mkdocs serve` to
preview or `mkdocs build --strict` to check links and build the site.
Navigation is configured in `mkdocs.yml`; retain `docs/SUMMARY.md` as the
Markdown table of contents.
