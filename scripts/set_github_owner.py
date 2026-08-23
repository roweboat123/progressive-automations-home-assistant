#!/usr/bin/env python3
"""Replace public-repository GitHub owner placeholders safely."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = "progressive-automations-home-assistant"
PLACEHOLDER = "__GITHUB_OWNER__"


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {Path(sys.argv[0]).name} GITHUB_USERNAME")
        return 2

    owner = sys.argv[1].strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner):
        print("That does not look like a valid GitHub username.")
        return 2

    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "custom_components" / "progressive_automations" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["documentation"] = f"https://github.com/{owner}/{REPO}#readme"
    manifest["issue_tracker"] = f"https://github.com/{owner}/{REPO}/issues"
    manifest["codeowners"] = [f"@{owner}"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8").replace(PLACEHOLDER, owner)
    readme_path.write_text(readme, encoding="utf-8")

    remaining = []
    for path in (manifest_path, readme_path):
        if PLACEHOLDER in path.read_text(encoding="utf-8"):
            remaining.append(path.relative_to(root))

    print(f"GitHub metadata set for @{owner}.")
    if remaining:
        print("Placeholder remains in public metadata:")
        for path in remaining:
            print(f"  - {path}")
        return 1

    print("Public GitHub metadata is finalized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
