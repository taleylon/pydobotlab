"""Write the changelog section of one version: the notes of its GitHub release.

Run by ``.github/workflows/publish.yml``, and by hand for older versions:

    python scripts/changelog_section.py 0.2.1 release-notes.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
LINK_REFERENCE = re.compile(r"\[[^\]]+\]: ")


def is_section_end(line: str) -> bool:
    """The heading of another version, or the link references at the end of the changelog."""
    return line.startswith("## [") or LINK_REFERENCE.match(line) is not None


def changelog_section(version: str, changelog: str) -> str:
    """The text under the ``## [version]`` heading, without the heading."""
    lines = changelog.splitlines()
    heading = f"## [{version}]"
    headings = [index for index, line in enumerate(lines) if line.startswith(heading)]
    if not headings:
        raise ValueError(f"the changelog has no section for {version}")
    start = headings[0]
    end = start + 1
    while end < len(lines) and not is_section_end(lines[end]):
        end += 1
    return "\n".join(lines[start + 1 : end]).strip() + "\n"


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: changelog_section.py VERSION OUTPUT_FILE", file=sys.stderr)
        return 2
    version, output_path = sys.argv[1], Path(sys.argv[2])
    try:
        section = changelog_section(version, CHANGELOG_PATH.read_text(encoding="utf-8"))
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    output_path.write_text(section, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
