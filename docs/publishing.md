# Publishing and maintaining the project

The intended GitHub repository is **taleylon/pydobotlab**. The documentation
homepage is **https://taleylon.github.io/pydobotlab/**. Both Homepage and
Documentation in the package metadata point there, so PyPI displays links
to the guide. These addresses become live after repository and Pages setup.

GitHub hosts the source and documentation. PyPI hosts the downloadable
package used by `python -m pip install pydobotlab`. They are separate accounts.

## Verify locally

```bash
python -m pip install -e ".[dev,gui,docs]"
ruff check .
ruff format --check .
python -m pytest --timeout=30
mkdocs build --strict
python -m build
python -m twine check --strict dist/*
```

`python -m build` creates a source archive and builds the wheel from that
archive. The CI workflow also installs the wheel into a separate virtual
environment and runs `scripts/check_installed_package.py` outside the source
import path. The package version is maintained in `pydobotlab/__init__.py`.

## Start the GitHub repository with fresh history

Use a separate directory containing the reviewed source files, including
`docs/`, `mkdocs.yml`, and `.github/workflows/`. Exclude the existing `.git`,
virtual environments, build output, caches, and package metadata directories.
Initialize that directory as a new repository; do not push this checkout's
GitLab history. The original history contains an AI co-author trailer.

Create the initial commit with author and committer
`Tal Eylon <taleylon1@gmail.com>`, without co-author trailers. Verify that this
email belongs to the `taleylon` GitHub account. Create an empty GitHub
repository named `pydobotlab`, then push the new `main` branch. This preserves
the original GitLab history and starts GitHub with a single clean commit.

## Publish the documentation homepage

1. In **taleylon/pydobotlab → Settings → Pages**, set the source to
   **GitHub Actions**.
2. Run **Documentation → Run workflow**, or push a documentation change to
   `main`. Pull requests build the site but do not deploy it.
3. Check https://taleylon.github.io/pydobotlab/ before publishing to PyPI.
4. Set the repository's About website to the same address.

The site uses Material for MkDocs with sidebar navigation, search, code
copy buttons, and a light/dark theme. Edit Markdown under `docs/`; update
both `mkdocs.yml` and `docs/SUMMARY.md` when adding pages. Preview locally:

```bash
python -m pip install -e ".[docs]"
mkdocs serve
```

Open http://127.0.0.1:8000/pydobotlab/ while the preview server is running.

## Configure package publishing

Create or sign into your own PyPI and TestPyPI accounts, verify your email,
and configure two-factor authentication. Check that `pydobotlab` is available
or already owned by you; its availability has not been established locally.

On each index, register a pending Trusted Publisher with these fields:

| Field | PyPI | TestPyPI |
| --- | --- | --- |
| Project | `pydobotlab` | `pydobotlab` |
| GitHub owner | `taleylon` | `taleylon` |
| Repository | `pydobotlab` | `pydobotlab` |
| Workflow filename | `publish.yml` | `publish.yml` |
| Environment | `pypi` | `testpypi` |

Create matching GitHub environments. Configure a required reviewer for
`pypi` to review production releases. Trusted Publishing uses short-lived
credentials supplied by GitHub Actions; no PyPI token belongs in the repository.

## Release

1. Finish reviewing the refactor and ensure CI and documentation checks pass.
2. Run **Publish package** manually with destination `testpypi`.
3. Install the exact test release into a fresh environment. Install runtime
   dependencies from PyPI first, then fetch only this package from TestPyPI:

   ```bash
   python -m pip install pyserial
   python -m pip install --no-deps --index-url https://test.pypi.org/simple/ pydobotlab==0.1.0
   python -c "import pydobotlab; print(pydobotlab.__version__)"
   ```

4. Tag the reviewed commit `v0.1.0` (matching `__version__`) and push the tag.
5. Run **Publish package** on that tag with destination `pypi` and review
   the deployment. The workflow reruns CI and uploads the checked artifacts.
6. Verify `python -m pip install pydobotlab` in a fresh environment and check
   the homepage links on the PyPI page.

Publishing is manual. An ordinary code push does not upload to either index.
Use a new version for every new release; an uploaded version cannot be replaced.

References: [PyPA packaging metadata](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/),
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/),
[GitHub Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
