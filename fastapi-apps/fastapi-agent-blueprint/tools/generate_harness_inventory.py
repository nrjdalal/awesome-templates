"""Generate the harness inventory from tracked assets and reviewed bucket decisions.

Discovery follows the former matrix Verification scope, not governor review tiers.
The JSON map supplies judgments only; it cannot silently add paths to the scope.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = "docs/ai/shared/harness-buckets.json"
OUTPUT_PATH = "docs/ai/shared/harness-inventory.csv"
BUCKETS = {"Keep", "Replace", "Overlay", "Drop"}
# Source: matrix Verification Tier 0. Local-only config is a declared optional row.
CONSTITUTIONAL = (
    "AGENTS.md",
    "CLAUDE.md",
    ".codex/config.toml",
    ".codex/hooks.json",
    ".claude/settings.json",
    ".gemini/settings.json",
    ".antigravity/plugin.json",
    ".antigravity/gemini-extension.json",
    ".antigravity/mcp_config.json",
    ".antigravity/permissions.json",
    ".mcp.json",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/ticket.yml",
    "docs/history/045-hybrid-harness-target-architecture.md",
)
LOCAL_ONLY = ".claude/settings.local.json"
SHARED_GROUPS = (
    ".agents/shared/governor/",
    "docs/history/archive/governor-review-log/",
)
# Named enforcement assets historically live in Tier 1 alongside shared references.
ENFORCEMENT = (
    "tools/check_governor_footer.py",
    "tools/check_context_budget.py",
    "tools/review_packet.py",
    "tools/generate_harness_inventory.py",
)
SKILL_ROOTS = ("docs/ai/shared/skills", ".claude/skills", ".agents/skills")
HOOK_ROOTS = (".claude/hooks/", ".codex/hooks/", ".antigravity/hooks/")
RULE_ROOTS = (".claude/rules/", ".codex/rules/", ".antigravity/rules/")


@dataclass(frozen=True)
class Asset:
    tier: int
    path: str
    status: str = "tracked"
    members: tuple[str, ...] = ()


def discover(tracked: set[str]) -> list[Asset]:
    """Enumerate stable logical assets; skill triples occupy one inventory row."""
    assets = [Asset(0, path) for path in CONSTITUTIONAL if path in tracked]
    required: set[str] = set(CONSTITUTIONAL)
    missing = required - tracked
    for path in SHARED_GROUPS:
        if not any(item.startswith(path) for item in tracked):
            missing.add(path)
        else:
            assets.append(Asset(1, path))
    for path in ENFORCEMENT:
        if path not in tracked:
            missing.add(path)
        else:
            assets.append(Asset(1, path))
    if missing:
        raise ValueError("Required scope assets missing: " + ", ".join(sorted(missing)))
    assets.append(Asset(0, LOCAL_ONLY, "local-only"))
    assets.extend(
        Asset(1, path)
        for path in tracked
        if PurePosixPath(path).parent == PurePosixPath("docs/ai/shared")
        and path.endswith(".md")
    )
    skills: dict[str, list[str]] = {}
    for path in tracked:
        posix = PurePosixPath(path)
        for root in SKILL_ROOTS:
            prefix = root + "/"
            if not path.startswith(prefix):
                continue
            relative = posix.relative_to(root)
            if (
                root.startswith("docs/")
                and len(relative.parts) == 1
                and path.endswith(".md")
            ):
                skills.setdefault(posix.stem, []).append(path)
            elif len(relative.parts) == 2 and relative.name == "SKILL.md":
                skills.setdefault(relative.parts[0], []).append(path)
    for name, members in sorted(skills.items()):
        expected = {
            f"docs/ai/shared/skills/{name}.md",
            f".claude/skills/{name}/SKILL.md",
            f".agents/skills/{name}/SKILL.md",
        }
        if set(members) != expected:
            raise ValueError(
                f"Incomplete skill triple {name}: missing {sorted(expected - set(members))}"
            )
        assets.append(
            Asset(2, f"docs/ai/shared/skills/{name}.md", members=tuple(sorted(members)))
        )
    for path in tracked:
        posix = PurePosixPath(path)
        if any(path.startswith(prefix) for prefix in HOOK_ROOTS):
            if "__pycache__" not in posix.parts and posix.suffix != ".pyc":
                assets.append(Asset(3, path))
        elif any(posix.parent == PurePosixPath(prefix) for prefix in RULE_ROOTS):
            if path.startswith(".codex/") or posix.suffix == ".md":
                assets.append(Asset(4, path))
    return sorted(assets, key=lambda asset: (asset.tier, asset.path))


def render(assets: list[Asset], decisions: dict, tracked: set[str]) -> str:
    """Fail on unmapped assets, obsolete judgments, and invalid Drop transitions."""
    if decisions.get("schema_version") != 1:
        raise ValueError("Unsupported bucket-map schema_version")
    mapping = decisions.get("buckets")
    retired = decisions.get("retired")
    if not isinstance(mapping, dict) or not isinstance(retired, dict):
        raise ValueError("Bucket map needs buckets object and retired object")
    if any(
        not isinstance(path, str) or type(tier) is not int or tier not in range(5)
        for path, tier in retired.items()
    ):
        raise ValueError("Retired paths need original inventory tier integers 0-4")
    required = {
        member for asset in assets for member in (asset.members or (asset.path,))
    }
    retired_set = set(retired)
    if required & retired_set or retired_set & tracked:
        raise ValueError("Retired asset exists in the active scope or git index")
    missing = (required | retired_set) - set(mapping)
    stale = set(mapping) - required - retired_set
    if missing or stale:
        raise ValueError(
            f"Bucket map mismatch: missing={sorted(missing)}, stale={sorted(stale)}"
        )
    if any(
        not isinstance(bucket, str) or bucket not in BUCKETS
        for bucket in mapping.values()
    ):
        raise ValueError("Unknown bucket; use Keep/Replace/Overlay/Drop")
    if any(mapping[path] != "Drop" for path in retired_set):
        raise ValueError("Retired assets must be Drop")
    if any(mapping[path] == "Drop" for path in required):
        raise ValueError(
            "Active assets cannot be Drop; remove and retire them explicitly"
        )
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("tier", "asset", "bucket", "status", "members"))
    for asset in assets:
        member_buckets = {mapping[path] for path in (asset.members or (asset.path,))}
        if len(member_buckets) != 1:
            raise ValueError(f"Skill triple buckets disagree: {asset.path}")
        writer.writerow(
            (
                asset.tier,
                asset.path,
                member_buckets.pop(),
                asset.status,
                ";".join(asset.members),
            )
        )
    for path in sorted(retired_set):
        writer.writerow((retired[path], path, "Drop", "retired", ""))
    return output.getvalue()


def tracked_files(root: Path) -> set[str]:
    result = subprocess.run(  # noqa: S603 -- fixed git argv
        ["git", "ls-files", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    return {
        path.decode("utf-8", errors="surrogateescape")
        for path in result.stdout.split(b"\0")
        if path
    }


def generate(root: Path) -> str:
    tracked = tracked_files(root)
    return render(discover(tracked), json.loads((root / MAP_PATH).read_text()), tracked)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if generated output differs"
    )
    args = parser.parse_args()
    try:
        expected = generate(ROOT)
        target = ROOT / OUTPUT_PATH
        if args.check:
            if not target.exists() or target.read_bytes() != expected.encode("utf-8"):
                raise ValueError(
                    "Inventory stale: run python3 tools/generate_harness_inventory.py and stage the output"
                )
        else:
            target.write_text(expected)
        rows = list(csv.DictReader(io.StringIO(expected)))
        counts = Counter(row["bucket"] for row in rows if row["status"] != "local-only")
        print(
            f"Harness inventory: {len(rows)} logical rows (including optional local config); tracked/retired buckets {dict(sorted(counts.items()))}"
        )
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Harness inventory: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
