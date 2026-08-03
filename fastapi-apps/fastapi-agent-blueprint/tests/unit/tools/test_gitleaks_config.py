"""Contract tests for `.gitleaks.toml` (#320).

gitleaks is the repo's committed-secret gate: `.pre-commit-config.yaml` pins
`v8.30.1` with no arguments, and CI runs `pre-commit run --all-files`. Before this
config existed the shipped default ruleset applied, which caught **Slack**
webhooks under any variable name but had **no** Discord webhook rule.

Verified by executing the pinned binary against a staged fixture of eight Discord
webhook shapes, one Slack control, and two placeholders. Before:

    slack-webhook-url    line 9        <- the control fired
    (nothing for 1-8)                 <- every Discord shape passed

After:

    discord-webhook-url  lines 1-8     <- including no-scheme, http://, UPPERCASE
    slack-webhook-url    line 9        <- defaults still loaded
    (nothing for 10-11)               <- placeholders still clean

Note when re-running that by hand: gitleaks reads `.gitleaks.toml` from the
**git index**, so an unstaged edit to the config is silently ignored and the run
appears to prove the old pattern. That cost one confusing round here.

The failure mode this file guards against is subtle and silent: a
`.gitleaks.toml` **without** `[extend] useDefault = true` *replaces* the built-in
ruleset rather than extending it, which would drop `slack-webhook-url` and every
other default rule while still appearing to work. Nothing else in the repo would
notice.

Scope note: these tests check the *config contract* — they do not execute
gitleaks, which lives in a pre-commit-managed environment and is not importable
here. The regex is exercised with Python's `re`; gitleaks uses Go's RE2. The
pattern deliberately uses only constructs common to both, but a behavioural claim
about gitleaks itself rests on the manual runs recorded above, not on these tests.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / ".gitleaks.toml"


@pytest.fixture(scope="module")
def config() -> dict:
    assert CONFIG_PATH.is_file(), f"{CONFIG_PATH} is missing"
    return tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def discord_rule(config) -> dict:
    rules = {rule["id"]: rule for rule in config.get("rules", [])}
    assert "discord-webhook-url" in rules, f"rules present: {sorted(rules)}"
    return rules["discord-webhook-url"]


class TestTheDefaultRulesetIsExtendedNotReplaced:
    def test_use_default_is_true(self, config):
        assert config.get("extend", {}).get("useDefault") is True, (
            "without `[extend] useDefault = true` this file REPLACES the built-in "
            "ruleset, silently dropping slack-webhook-url and every other default "
            "rule while still appearing to work"
        )

    def test_no_global_allowlist_was_introduced(self, config):
        """A repo-wide allowlist would weaken every default rule at once, which is
        the opposite of what this config is for."""
        assert "allowlist" not in config, (
            "a top-level allowlist suppresses findings across the whole default "
            "ruleset — scope any exemption to the rule that needs it"
        )


class TestTheDiscordRuleMatchesRealWebhooks:
    ID = "123456789012345678"
    # Deliberately low-entropy and assembled rather than written as one literal.
    # The rule keys on *shape* — `\d+/[\w-]+` with no entropy floor — so a
    # realistic-looking token adds nothing, and the first draft of this file used
    # one and was rejected by this repo's own gate: the default `generic-api-key`
    # rule fired on it at entropy 5.35. Using a shape-only token also proves the
    # Discord rule does not secretly depend on entropy to fire.
    TOKEN = "fake-webhook-token-" + "0" * 24

    @pytest.mark.parametrize(
        "scheme,host,api,suffix",
        [
            # Hosts and API versions Discord actually serves.
            ("https://", "discord.com", "api", ""),
            ("https://", "ptb.discord.com", "api", ""),
            ("https://", "canary.discord.com", "api", ""),
            ("https://", "discordapp.com", "api", ""),
            ("https://", "discord.com", "api/v10", ""),
            ("https://", "discord.com", "api/v9", ""),
            # The three shapes a self-check found the first version of this rule
            # missing. The leaked credential is the id/token pair; the scheme is
            # decoration, and a value pasted without one is still usable.
            ("", "discord.com", "api", ""),
            ("http://", "discord.com", "api", ""),
            ("https://", "DISCORD.COM", "api", ""),
            ("HTTPS://", "Discord.Com", "api", ""),
            # Discord's execution suffixes and a common query parameter. These
            # need no special handling — the pattern is unanchored at the end, so
            # it matches the credential inside them.
            ("https://", "discord.com", "api", "/slack"),
            ("https://", "discord.com", "api", "/github"),
            ("https://", "discord.com", "api", "?wait=true"),
        ],
    )
    def test_every_real_webhook_shape_matches(
        self, discord_rule, scheme, host, api, suffix
    ):
        url = f"{scheme}{host}/{api}/webhooks/{self.ID}/{self.TOKEN}{suffix}"
        assert re.search(discord_rule["regex"], url), (
            f"a real Discord webhook at {url!r} would not be blocked"
        )

    def test_the_rule_is_case_insensitive_by_construction(self, discord_rule):
        """Pinned separately because the `(?i)` flag is easy to drop when editing
        the pattern, and losing it silently reopens the uppercase-host hole."""
        assert discord_rule["regex"].startswith("(?i)"), (
            "the case-insensitive flag was removed; https://DISCORD.COM/... would "
            "no longer be blocked"
        )

    def test_it_matches_regardless_of_the_variable_name(self, discord_rule):
        """The point of matching the whole URL: `slack-webhook-url` is
        name-agnostic, and #286 raised the number of variable names a Discord
        webhook can hide behind from one to three."""
        url = f"https://discord.com/api/webhooks/{self.ID}/{self.TOKEN}"
        for name in (
            "DISCORD_WEBHOOK_URL",
            "NOTIFICATION_WARNING_WEBHOOK_URL",
            "NOTIFICATION_CRITICAL_WEBHOOK_URL",
            "anything_at_all",
        ):
            assert re.search(discord_rule["regex"], f"{name}={url}"), name


class TestThePlaceholdersInTheRepoStayClean:
    """These files deliberately commit truncated examples. The rule is specific
    enough that they cannot match, which is why it carries no allowlist — an
    unnecessary allowlist entry is a permanent hole."""

    PLACEHOLDERS = [
        "https://discord.com/api/webhooks/...",
        "https://discord.com/api/webhooks/<id>/<token>",
        "https://discord.com/api/webhooks/",
        "https://discord.com/api/webhooks/<channel_id>/<webhook_token>",
    ]

    @pytest.mark.parametrize("placeholder", PLACEHOLDERS)
    def test_placeholder_does_not_match(self, discord_rule, placeholder):
        assert not re.search(discord_rule["regex"], placeholder), (
            f"{placeholder!r} would fail the hook on every commit"
        )

    def test_the_committed_placeholders_are_still_the_shapes_tested_above(self):
        """If someone replaces a placeholder with a different shape, this test
        points at the file rather than letting CI fail mysteriously later."""
        tracked = [
            REPO_ROOT / "_env" / "local.env.example",
            REPO_ROOT / "docs" / "operations" / "error-notifications.md",
        ]
        pattern = re.compile(r"https://[\w.]*discord(?:app)?\.com/api/\S*")
        found: list[str] = []
        for path in tracked:
            if path.is_file():
                found += pattern.findall(path.read_text(encoding="utf-8"))
        assert found, "expected at least one committed Discord placeholder"
        for url in found:
            assert "..." in url or "<" in url, (
                f"{url!r} looks like a real webhook, not a placeholder"
            )


class TestTheTwoEnforcementPointsUseOneVersion:
    """The pre-commit hook scans the staged diff; the CI job scans the whole tree.
    They are separate invocations, so the pinned version can silently diverge —
    at which point local and CI enforce different rulesets.

    Context worth keeping: `pre-commit run --all-files` does NOT scan the tree.
    The hook is `gitleaks git --pre-commit --staged` with `pass_filenames: false`,
    so on a clean checkout it reports `0 commits scanned. scanned ~0 bytes`. That
    is why the CI job runs `gitleaks dir` separately, and why a green
    `--all-files` must not be read as "the tree is clean".
    """

    def test_ci_pins_the_same_version_as_pre_commit(self):
        pre_commit = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )

        hook_rev = re.search(r"gitleaks/gitleaks\s*\n\s*rev:\s*v([\d.]+)", pre_commit)
        assert hook_rev, "could not find the gitleaks rev in .pre-commit-config.yaml"

        ci_version = re.search(r'GITLEAKS_VERSION:\s*"([\d.]+)"', ci)
        assert ci_version, "could not find GITLEAKS_VERSION in ci.yml"

        assert hook_rev.group(1) == ci_version.group(1), (
            f"pre-commit pins v{hook_rev.group(1)} but CI pins "
            f"v{ci_version.group(1)} - local and CI would enforce different rulesets"
        )

    def test_ci_scans_the_directory_not_the_staged_diff(self):
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        assert "gitleaks dir" in ci, (
            "the CI job no longer runs a full-tree scan; `pre-commit run --all-files` "
            "alone scans nothing, so the secret gate would be local-only again"
        )
