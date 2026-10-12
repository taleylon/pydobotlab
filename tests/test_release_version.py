"""Release rule: a merged version branch publishes its version, which may only go up."""

from __future__ import annotations

import importlib.util
import io
import json
import urllib.error
from pathlib import Path

import pytest
from packaging.version import Version

SCRIPT = Path(__file__).parent.parent / "scripts" / "check_release_version.py"
spec = importlib.util.spec_from_file_location("check_release_version", SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

PUBLISHED = [Version("0.1.0"), Version("0.1.0.1")]


def respond_with(monkeypatch, body) -> list:
    """Make urlopen return ``body`` as JSON; return the list of requests made."""
    requests = []

    def urlopen(request, timeout):
        requests.append(request)
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(release.urllib.request, "urlopen", urlopen)
    return requests


# -- merging into main ----------------------------------------------------------------


def test_merging_the_version_branch_of_a_higher_version_publishes():
    assert release.should_publish_merge(Version("0.2"), PUBLISHED, "v0.2")
    assert release.should_publish_merge(Version("0.2.1"), PUBLISHED, "v0.2.1")


def test_branch_and_version_compare_as_versions():
    assert release.should_publish_merge(Version("0.2.0"), PUBLISHED, "v0.2")


def test_merging_a_published_version_is_skipped():
    assert not release.should_publish_merge(Version("0.1.0.1"), PUBLISHED, "v0.1.0.1")


@pytest.mark.parametrize("branch", ["v0.1.0", "v0.0.9"])
def test_a_lower_version_is_refused(branch):
    version = Version(branch[1:])
    with pytest.raises(release.ReleaseError, match="may only go up"):
        release.should_publish_merge(version, PUBLISHED, branch)


def test_a_branch_that_does_not_match_the_version_is_refused():
    with pytest.raises(release.ReleaseError, match="v0.3 does not match __version__ 0.2"):
        release.should_publish_merge(Version("0.2"), PUBLISHED, "v0.3")


@pytest.mark.parametrize("branch", ["", "main", "feature/config", "v0.2-docs", "version0.2", "v"])
def test_other_merges_and_direct_pushes_publish_nothing(branch):
    assert not release.should_publish_merge(Version("0.2"), PUBLISHED, branch)


def test_the_first_version_of_a_new_package_is_published():
    assert release.should_publish_merge(Version("0.1.0"), [], "v0.1.0")


def test_merged_branch_is_the_source_of_the_merged_pull_request(monkeypatch):
    requests = respond_with(
        monkeypatch,
        [
            {"merged_at": None, "head": {"ref": "draft"}},
            {"merged_at": "2026-10-12T10:00:00Z", "head": {"ref": "v0.2"}},
        ],
    )
    assert release.merged_branch("taleylon/pydobotlab", "abc123", "token") == "v0.2"
    assert requests[0].full_url.endswith("/repos/taleylon/pydobotlab/commits/abc123/pulls")
    assert requests[0].get_header("Authorization") == "Bearer token"


def test_a_direct_push_has_no_merged_branch(monkeypatch):
    respond_with(monkeypatch, [])
    assert release.merged_branch("taleylon/pydobotlab", "abc123", "") == ""


# -- manual runs ----------------------------------------------------------------------


def test_a_manual_pypi_release_needs_the_matching_tag():
    version = Version("0.2")
    assert release.should_publish_manual(
        version, PUBLISHED, ref="refs/tags/v0.2", destination="pypi"
    )
    with pytest.raises(release.ReleaseError, match="tag v0.2"):
        release.should_publish_manual(version, PUBLISHED, ref="refs/heads/main", destination="pypi")


def test_a_manual_testpypi_release_runs_from_any_ref():
    assert release.should_publish_manual(
        Version("0.2"), PUBLISHED, ref="refs/heads/main", destination="testpypi"
    )


# -- reading versions -----------------------------------------------------------------


def test_the_version_is_read_from_the_package(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('"""Package."""\n\n__version__ = "0.2"\n', encoding="utf-8")
    assert release.package_version(init) == Version("0.2")
    assert release.package_version() == Version(__import__("pydobotlab").__version__)


def test_published_versions_reads_the_index(monkeypatch):
    respond_with(monkeypatch, {"releases": {"0.1.0": [], "0.1.0.1": [], "not-a-version": []}})
    assert release.published_versions("https://example.invalid") == PUBLISHED


def test_a_package_missing_from_the_index_has_no_versions(monkeypatch):
    def not_found(url, timeout):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(release.urllib.request, "urlopen", not_found)
    assert release.published_versions("https://example.invalid") == []
