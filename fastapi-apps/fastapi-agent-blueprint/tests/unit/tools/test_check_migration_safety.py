"""Tests for tools/check_migration_safety.py (ADR 056)."""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = REPO_ROOT / "tools" / "check_migration_safety.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_migration_safety", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_migration_safety"] = module
    spec.loader.exec_module(module)
    return module


cms = _load_module()


def _write(tmp_path: Path, rel_path: str, content: str) -> Path:
    target = tmp_path / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _rev(
    tmp_path: Path,
    name: str,
    upgrade_body: str,
    downgrade_body: str = "    pass",
) -> Path:
    content = (
        "from alembic import op\n"
        "import sqlalchemy as sa\n\n\n"
        "def upgrade():\n"
        f"{upgrade_body}\n\n\n"
        "def downgrade():\n"
        f"{downgrade_body}\n"
    )
    return _write(tmp_path, f"migrations/versions/{name}.py", content)


def _rule_ids(findings) -> set[str]:
    return {f.rule_id for f in findings}


class TestSafeOperations:
    def test_create_table_is_clean(self, tmp_path):
        target = _rev(
            tmp_path,
            "0001_create",
            "    op.create_table(\n"
            '        "widget",\n'
            '        sa.Column("id", sa.Integer(), nullable=False),\n'
            '        sa.Column("name", sa.String(length=50), nullable=False),\n'
            '        sa.PrimaryKeyConstraint("id"),\n'
            "    )",
        )
        assert cms.find_findings(target, repo_root=tmp_path) == []

    def test_add_nullable_column_is_clean(self, tmp_path):
        target = _rev(
            tmp_path,
            "0002_add_nullable",
            '    op.add_column("widget", sa.Column("note", sa.String(), nullable=True))',
        )
        assert cms.find_findings(target, repo_root=tmp_path) == []

    def test_concurrent_index_is_clean(self, tmp_path):
        target = _rev(
            tmp_path,
            "0003_conc_index",
            "    op.create_index(\n"
            '        "ix_widget_name", "widget", ["name"],\n'
            "        postgresql_concurrently=True,\n"
            "    )",
        )
        assert cms.find_findings(target, repo_root=tmp_path) == []

    def test_ops_on_table_created_in_same_upgrade_are_clean(self, tmp_path):
        # Index + NOT NULL column + constraint on a freshly created (empty)
        # table cannot block live traffic — must not be flagged.
        target = _rev(
            tmp_path,
            "0003b_new_table",
            "    op.create_table(\n"
            '        "gadget",\n'
            '        sa.Column("id", sa.Integer(), nullable=False),\n'
            '        sa.Column("code", sa.String(), nullable=False),\n'
            '        sa.PrimaryKeyConstraint("id"),\n'
            "    )\n"
            '    op.create_index("ix_gadget_code", "gadget", ["code"])\n'
            '    op.add_column("gadget", sa.Column("extra", sa.String(), nullable=False))\n'
            '    op.create_unique_constraint("uq_gadget_code", "gadget", ["code"])',
        )
        assert cms.find_findings(target, repo_root=tmp_path) == []

    def test_index_on_preexisting_table_is_flagged_even_with_a_create(self, tmp_path):
        # Creating one table does not whitelist a blocking index on another.
        target = _rev(
            tmp_path,
            "0003c_mixed",
            "    op.create_table(\n"
            '        "gadget",\n'
            '        sa.Column("id", sa.Integer(), nullable=False),\n'
            '        sa.PrimaryKeyConstraint("id"),\n'
            "    )\n"
            '    op.create_index("ix_widget_name", "widget", ["name"])',
        )
        assert _rule_ids(cms.find_findings(target, repo_root=tmp_path)) == {
            "blocking-index"
        }

    def test_batch_alter_on_same_created_table_is_exempt(self, tmp_path):
        # batch_alter_table on a table created in this same upgrade is empty.
        target = _rev(
            tmp_path,
            "0003d_batch_new",
            "    op.create_table(\n"
            '        "gadget",\n'
            '        sa.Column("id", sa.Integer(), nullable=False),\n'
            '        sa.PrimaryKeyConstraint("id"),\n'
            "    )\n"
            '    with op.batch_alter_table("gadget") as batch_op:\n'
            '        batch_op.add_column(sa.Column("code", sa.String(), nullable=False))',
        )
        assert cms.find_findings(target, repo_root=tmp_path) == []

    def test_keyword_create_table_exempts_later_ops(self, tmp_path):
        # create_table(table_name=...) keyword form must still exempt the index.
        target = _rev(
            tmp_path,
            "0003e_kw_create",
            '    op.create_table(table_name="gadget")\n'
            '    op.create_index("ix_gadget_id", "gadget", ["id"])',
        )
        assert cms.find_findings(target, repo_root=tmp_path) == []


class TestUnsafeOperations:
    def test_add_not_null_without_default(self, tmp_path):
        target = _rev(
            tmp_path,
            "0004_add_notnull",
            '    op.add_column("widget", sa.Column("code", sa.String(), nullable=False))',
        )
        findings = cms.find_findings(target, repo_root=tmp_path)
        assert _rule_ids(findings) == {"add-not-null-no-default"}
        assert findings[0].severity == cms.SEV_UNSAFE

    def test_add_not_null_with_default_is_caution(self, tmp_path):
        target = _rev(
            tmp_path,
            "0005_add_notnull_default",
            "    op.add_column(\n"
            '        "widget",\n'
            '        sa.Column("flag", sa.Boolean(), nullable=False, server_default="0"),\n'
            "    )",
        )
        findings = cms.find_findings(target, repo_root=tmp_path)
        assert _rule_ids(findings) == {"add-not-null-with-default"}
        assert findings[0].severity == cms.SEV_CAUTION

    def test_client_default_without_server_default_is_unsafe(self, tmp_path):
        # A client-side `default=` does not backfill existing rows.
        target = _rev(
            tmp_path,
            "0004b_client_default",
            "    op.add_column(\n"
            '        "widget",\n'
            '        sa.Column("code", sa.String(), nullable=False, default="x"),\n'
            "    )",
        )
        findings = cms.find_findings(target, repo_root=tmp_path)
        assert _rule_ids(findings) == {"add-not-null-no-default"}
        assert findings[0].severity == cms.SEV_UNSAFE

    def test_server_default_none_is_unsafe(self, tmp_path):
        target = _rev(
            tmp_path,
            "0004c_sd_none",
            "    op.add_column(\n"
            '        "widget",\n'
            '        sa.Column("code", sa.String(), nullable=False, server_default=None),\n'
            "    )",
        )
        assert _rule_ids(cms.find_findings(target, repo_root=tmp_path)) == {
            "add-not-null-no-default"
        }

    def test_blocking_index(self, tmp_path):
        target = _rev(
            tmp_path,
            "0006_index",
            '    op.create_index("ix_widget_name", "widget", ["name"])',
        )
        assert _rule_ids(cms.find_findings(target, repo_root=tmp_path)) == {
            "blocking-index"
        }

    def test_drop_column_is_caution(self, tmp_path):
        target = _rev(
            tmp_path,
            "0007_drop",
            '    op.drop_column("widget", "note")',
        )
        findings = cms.find_findings(target, repo_root=tmp_path)
        assert _rule_ids(findings) == {"drop-column"}
        assert findings[0].severity == cms.SEV_CAUTION

    def test_rename_and_type_change(self, tmp_path):
        target = _rev(
            tmp_path,
            "0008_alter",
            '    op.alter_column("widget", "name", new_column_name="title")\n'
            '    op.alter_column("widget", "code", type_=sa.Integer())\n'
            '    op.alter_column("widget", "note", nullable=False)',
        )
        assert _rule_ids(cms.find_findings(target, repo_root=tmp_path)) == {
            "rename-column",
            "type-change",
            "set-not-null",
        }

    def test_rename_table(self, tmp_path):
        target = _rev(
            tmp_path,
            "0009_rename_table",
            '    op.rename_table("widget", "gadget")',
        )
        assert _rule_ids(cms.find_findings(target, repo_root=tmp_path)) == {
            "rename-table"
        }

    def test_unique_constraint_rule(self, tmp_path):
        target = _rev(
            tmp_path,
            "0010_unique",
            '    op.create_unique_constraint("uq_widget_name", "widget", ["name"])',
        )
        # UNIQUE is its own rule — NOT VALID does not apply to it.
        assert _rule_ids(cms.find_findings(target, repo_root=tmp_path)) == {
            "unique-constraint"
        }

    def test_fk_constraint_rule(self, tmp_path):
        target = _rev(
            tmp_path,
            "0010b_fk",
            '    op.create_foreign_key("fk_w_g", "widget", "gadget", ["gid"], ["id"])',
        )
        assert _rule_ids(cms.find_findings(target, repo_root=tmp_path)) == {
            "add-constraint-blocking"
        }

    def test_batch_op_add_column_is_detected(self, tmp_path):
        target = _rev(
            tmp_path,
            "0011_batch",
            '    with op.batch_alter_table("widget") as batch_op:\n'
            '        batch_op.add_column(sa.Column("code", sa.String(), nullable=False))',
        )
        assert _rule_ids(cms.find_findings(target, repo_root=tmp_path)) == {
            "add-not-null-no-default"
        }


class TestScope:
    def test_downgrade_drops_are_not_flagged(self, tmp_path):
        target = _rev(
            tmp_path,
            "0012_symmetric",
            '    op.add_column("widget", sa.Column("note", sa.String(), nullable=True))',
            downgrade_body='    op.drop_column("widget", "note")',
        )
        # upgrade is a safe nullable add; the downgrade drop must not be flagged.
        assert cms.find_findings(target, repo_root=tmp_path) == []

    def test_unparseable_is_reported(self, tmp_path):
        target = _write(
            tmp_path, "migrations/versions/0013_broken.py", "def upgrade(:\n"
        )
        findings = cms.find_findings(target, repo_root=tmp_path)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable"


class TestRun:
    def test_advisory_mode_returns_zero_with_findings(self, tmp_path, capsys):
        _rev(
            tmp_path,
            "0004_add_notnull",
            '    op.add_column("widget", sa.Column("code", sa.String(), nullable=False))',
        )
        exit_code = cms.run(
            ["migrations/versions/0004_add_notnull.py"], repo_root=tmp_path
        )
        assert exit_code == 0  # advisory-first (ADR056-G1)
        out = capsys.readouterr().out
        assert "1 advisory finding" in out
        assert "add-not-null-no-default" in out

    def test_strict_mode_returns_one_with_findings(self, tmp_path, capsys):
        _rev(
            tmp_path,
            "0004_add_notnull",
            '    op.add_column("widget", sa.Column("code", sa.String(), nullable=False))',
        )
        exit_code = cms.run(
            ["--strict", "migrations/versions/0004_add_notnull.py"],
            repo_root=tmp_path,
        )
        assert exit_code == 1
        assert "add-not-null-no-default" in capsys.readouterr().err

    def test_clean_file_passes(self, tmp_path, capsys):
        _rev(
            tmp_path,
            "0002_add_nullable",
            '    op.add_column("widget", sa.Column("note", sa.String(), nullable=True))',
        )
        exit_code = cms.run(
            ["migrations/versions/0002_add_nullable.py"], repo_root=tmp_path
        )
        assert exit_code == 0
        assert "0 advisories" in capsys.readouterr().out

    def test_paths_outside_versions_are_ignored(self, tmp_path, capsys):
        _write(
            tmp_path,
            "src/widget/model.py",
            '    op.drop_column("widget", "note")\n',
        )
        exit_code = cms.run(["src/widget/model.py"], repo_root=tmp_path)
        assert exit_code == 0
        assert "0 advisories across 0 revision file(s)" in capsys.readouterr().out


class TestRealRepo:
    def test_scan_of_tracked_revisions_does_not_crash(self):
        """Advisory scan of the live revisions must run and stay non-blocking."""
        exit_code = cms.run([], repo_root=REPO_ROOT)
        assert exit_code == 0  # advisory: findings never fail the default run

    def test_discovery_returns_only_python_revisions(self):
        files = cms.discover_tracked_revisions(REPO_ROOT)
        assert files, "expected tracked revision files"
        assert all(path.suffix == ".py" for path in files)
        assert all("__pycache__" not in path.parts for path in files)
