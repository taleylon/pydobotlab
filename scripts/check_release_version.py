"""Decide whether the publish workflow uploads this version.

Run by ``.github/workflows/publish.yml``.

* On a push to ``main``: publish when the push merged a pull request from a
  version branch (``v0.2``, ``v1.0.1``, ...) whose name matches ``__version__``
  in ``pydobotlab/__init__.py``, and that version is higher than every version
  already on the package index. Other merges are skipped.
* On a manual run: publish to TestPyPI from any ref, or to PyPI from the tag
  ``v<version>``, when the version is higher than every published version.

The version may only go up: a version lower than a published one is an error,
and a version that is already published is skipped.

Environment: ``DESTINATION`` (``pypi`` or ``testpypi``), ``GITHUB_TOKEN``, and
the defaults ``GITHUB_EVENT_NAME``, ``GITHUB_REF``, ``GITHUB_REPOSITORY``,
``GITHUB_SHA``, and ``GITHUB_OUTPUT`` (receives ``publish=true|false`` and
``version=<version>``).
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from packaging.version import InvalidVersion, Version

INDEX_URLS = {
    "pypi": "https://pypi.org/pypi/pydobotlab/json",
    "testpypi": "https://test.pypi.org/pypi/pydobotlab/json",
}
INIT_PATH = Path(__file__).resolve().parent.parent / "pydobotlab" / "__init__.py"
VERSION_BRANCH = re.compile(r"v(\d+(?:\.\d+)*)")


class ReleaseError(Exception):
    """This version must not be published."""


def package_version(init_path: Path = INIT_PATH) -> Version:
    """The ``__version__`` assigned in ``pydobotlab/__init__.py``."""
    module = ast.parse(init_path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        ):
            return Version(ast.literal_eval(node.value))
    raise ReleaseError(f"no __version__ in {init_path}")


def published_versions(index_url: str) -> list[Version]:
    """Versions on the package index; empty if the package is not there yet."""
    try:
        with urllib.request.urlopen(index_url, timeout=30) as response:
            releases = json.load(response)["releases"]
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return []
        raise
    versions = []
    for text in releases:
        try:
            versions.append(Version(text))
        except InvalidVersion:
            continue
    return versions


def merged_branch(repository: str, sha: str, token: str) -> str:
    """Source branch of the merged pull request that produced commit ``sha``; empty if none."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/commits/{sha}/pulls", headers=headers
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        pulls = json.load(response)
    for pull in pulls:
        if pull.get("merged_at"):
            return pull["head"]["ref"]
    return ""


def branch_version(branch: str) -> Version | None:
    """The version a branch is named after (``v0.2`` -> ``0.2``); ``None`` for other names."""
    match = VERSION_BRANCH.fullmatch(branch)
    return Version(match.group(1)) if match else None


def is_new_version(version: Version, published: list[Version]) -> bool:
    """``True`` for a version above every published one, ``False`` if already published."""
    if published and version < max(published):
        raise ReleaseError(
            f"version {version} is lower than the published {max(published)}; "
            "the version may only go up"
        )
    return version not in published


def should_publish_merge(version: Version, published: list[Version], branch: str) -> bool:
    """Decision for a push to main that merged ``branch`` (empty: no merged pull request)."""
    named_version = branch_version(branch)
    if named_version is None:
        return False
    if named_version != version:
        raise ReleaseError(f"branch {branch} does not match __version__ {version}")
    return is_new_version(version, published)


def should_publish_manual(
    version: Version, published: list[Version], *, ref: str, destination: str
) -> bool:
    """Decision for a manual run from ``ref``."""
    if destination == "pypi" and ref != f"refs/tags/v{version}":
        raise ReleaseError(f"start a manual PyPI release from the tag v{version}")
    return is_new_version(version, published)


def main() -> int:
    destination = os.environ.get("DESTINATION", "pypi")
    version = package_version()
    published = published_versions(INDEX_URLS[destination])
    message = None
    try:
        if os.environ.get("GITHUB_EVENT_NAME") == "push":
            branch = merged_branch(
                os.environ["GITHUB_REPOSITORY"],
                os.environ["GITHUB_SHA"],
                os.environ.get("GITHUB_TOKEN", ""),
            )
            publish = should_publish_merge(version, published, branch)
            if branch_version(branch) is None:
                message = f"merged branch {branch!r} is not a version branch; no release"
        else:
            ref = os.environ.get("GITHUB_REF", "")
            publish = should_publish_manual(version, published, ref=ref, destination=destination)
    except ReleaseError as error:
        print(f"::error::{error}")
        return 1
    if message is None:
        message = (
            f"publishing {version} to {destination}"
            if publish
            else f"{version} is already on {destination}"
        )
    print(f"::notice::{message}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as file:
            file.write(f"publish={'true' if publish else 'false'}\n")
            file.write(f"version={version}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
