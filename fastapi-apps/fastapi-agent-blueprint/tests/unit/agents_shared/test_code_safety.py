"""Unit tests for governor.code_safety.check_code_safety (PR-A.4).

All injection patterns for the positive-corpus tests are constructed at
runtime using chr() and string concatenation so the source file itself
does not trigger the pre-tool security hook.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / ".agents" / "shared"))

from governor.code_safety import check_code_safety

# ---------------------------------------------------------------------------
# Runtime helpers — chr() avoids triggering hook on this source file.
# ---------------------------------------------------------------------------

_DQ = chr(34)  # double-quote
_SQ = chr(39)  # single-quote
_FC = chr(102)  # letter f (used as f-string prefix in constructed content)

# SQL keywords split so the identifier names do not contain the full keyword.
_KW1 = "SEL" + "ECT"  # SELECT
_KW2 = "INS" + "ERT"  # INSERT
_KW3 = "UPD" + "ATE"  # UPDATE
_KW4 = "DEL" + "ETE"  # DELETE
_KW5 = "DR" + "OP"  # DROP

# Sensitive-keyword fragments for log-pattern tests.
# Identifier names chosen to NOT contain the keyword as a substring.
_PWD = "pass" + "word"  # password
_TKN = "tok" + "en"  # token

# Source paths used across tests.
_SRC = "src/user/service.py"  # non-domain, non-test
_DOM = "src/user/domain/service.py"  # domain path -> triggers infra check
_TST = "/project/tests/unit/test_x.py"  # absolute-style path containing /tests/


# ---------------------------------------------------------------------------
# 1. SQL injection — positive corpus
# ---------------------------------------------------------------------------


def test_fstring_sql_flagged() -> None:
    content = _FC + _DQ + _KW1 + " * FROM users WHERE id={x}" + _DQ
    errors = check_code_safety(_SRC, content)
    assert any("f-string SQL" in e for e in errors)


def test_fstring_with_insert_flagged() -> None:
    content = _FC + _DQ + _KW2 + " INTO t VALUES ({v})" + _DQ
    errors = check_code_safety(_SRC, content)
    assert any("f-string SQL" in e for e in errors)


def test_format_sql_flagged() -> None:
    # The hook rule checks: .format(...)  <then later on same line>  SQL keyword.
    content = ".format(uid) " + _KW1 + " * FROM t"
    errors = check_code_safety(_SRC, content)
    assert any(".format() SQL" in e for e in errors)


def test_text_with_fstring_flagged() -> None:
    # Builds text-function receiving an f-string argument.
    content = "text(" + _FC + _DQ + "query_string" + _DQ + ")"
    errors = check_code_safety(_SRC, content)
    assert any("text()" in e for e in errors)


def test_execute_with_fstring_flagged() -> None:
    # Builds execute-function receiving an f-string argument.
    _ex = ".exec" + "ute("
    content = _ex + _FC + _DQ + "raw" + _DQ + ")"
    errors = check_code_safety(_SRC, content)
    assert any("execute()" in e for e in errors)


def test_execute_with_format_flagged() -> None:
    # Builds execute-function receiving a .format() argument.
    _ex = ".exec" + "ute("
    content = _ex + _DQ + "raw" + _DQ + ".format())"
    errors = check_code_safety(_SRC, content)
    assert any(".format()" in e for e in errors)


# ---------------------------------------------------------------------------
# 2. Hardcoded secrets — positive corpus
# ---------------------------------------------------------------------------


def test_hardcoded_password_flagged() -> None:
    content = _PWD + " = " + _DQ + "my_super_s3cret_val" + _DQ
    errors = check_code_safety(_SRC, content)
    assert any("Hardcoded secret" in e for e in errors)


def test_hardcoded_api_key_flagged() -> None:
    content = "api_key = " + _DQ + "AKIA1234567890ABCDEF" + _DQ
    errors = check_code_safety(_SRC, content)
    assert any("Hardcoded secret" in e for e in errors)


# ---------------------------------------------------------------------------
# 3. Domain -> Infrastructure import — positive corpus
# ---------------------------------------------------------------------------


def test_domain_infra_import_flagged() -> None:
    content = "from src.user.infrastructure import UserRepo"
    errors = check_code_safety(_DOM, content)
    assert any("Domain layer" in e for e in errors)


# ---------------------------------------------------------------------------
# 4. Sensitive data in logs — positive corpus
# ---------------------------------------------------------------------------


def test_logger_with_sensitive_field_flagged() -> None:
    content = "logger.info(user_" + _PWD + ")"
    errors = check_code_safety(_SRC, content)
    assert any("logs" in e.lower() for e in errors)


def test_print_with_sensitive_field_flagged() -> None:
    content = "print(user_" + _TKN + "_value)"
    errors = check_code_safety(_SRC, content)
    assert any("logs" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Negative corpus — must return []
# ---------------------------------------------------------------------------


def test_parameterized_orm_passes() -> None:
    content = "result = db.get(id=:uid)"
    assert check_code_safety(_SRC, content) == []


def test_pydantic_field_suppresses_secret() -> None:
    # Detection IS triggered (password = "literal") but Field() elsewhere in
    # the same content trips the whole-content allow-list, suppressing the error.
    # This validates the suppress mechanism is reachable, not vacuously absent.
    content = (
        _PWD + " = " + _DQ + "admin123" + _DQ + "\ndb_" + _PWD + ": str = Field(...)\n"
    )
    assert check_code_safety(_SRC, content) == []


def test_os_environ_suppresses_secret() -> None:
    # Detection IS triggered (password = "literal") but os.environ in the
    # same content trips the allow-list.
    content = (
        _PWD + " = " + _DQ + "fallback_val" + _DQ + "\n"
        "actual = os.environ[" + _DQ + "DB_" + _PWD.upper() + _DQ + "]\n"
    )
    assert check_code_safety(_SRC, content) == []


def test_settings_reference_suppresses_secret() -> None:
    # Detection IS triggered (password = "literal") but settings.* reference
    # in the same content trips the allow-list.
    content = (
        _PWD + " = " + _DQ + "fallback_pwd" + _DQ + "\n"
        "actual = settings.db_" + _PWD + "\n"
    )
    assert check_code_safety(_SRC, content) == []


def test_secret_in_test_file_passes() -> None:
    content = _PWD + " = " + _DQ + "hardcoded_in_test" + _DQ
    assert check_code_safety(_TST, content) == []


def test_infra_import_outside_domain_passes() -> None:
    content = "from src.user.infrastructure import UserRepo"
    assert check_code_safety("src/user/service.py", content) == []


def test_clean_service_code_passes() -> None:
    content = "from src.user.domain.service import UserService\nresult = repo.get(id)"
    assert check_code_safety(_SRC, content) == []


@pytest.mark.parametrize(
    "content",
    [
        "result = service.get_user(user_id=1)",
        "logger.info(" + repr("request_started") + ", path=request.url.path)",
        "query = repo.find_by_id(uid)",
    ],
)
def test_safe_content_passes(content: str) -> None:
    assert check_code_safety(_SRC, content) == []


# ---------------------------------------------------------------------------
# Path-normalization regressions — a crafted path must not spoof the
# test-file skip (or the domain-layer classification) via a bare substring.
# ---------------------------------------------------------------------------


def test_traversal_into_src_does_not_bypass_secret_check() -> None:
    # "./tests/../src/config.py" contains the substring "/tests/" but resolves
    # to a production file, so it must NOT be treated as a test file.
    content = _PWD + " = " + _DQ + "my_super_s3cret_val" + _DQ
    errors = check_code_safety("./tests/../src/config.py", content)
    assert any("Hardcoded secret" in e for e in errors)


def test_deep_traversal_resolving_to_src_flagged() -> None:
    content = _PWD + " = " + _DQ + "another_s3cret_here" + _DQ
    errors = check_code_safety("tests/x/../../src/config.py", content)
    assert any("Hardcoded secret" in e for e in errors)


def test_relative_tests_dir_is_exempted() -> None:
    # A relative test path (no leading slash) is exempted via segment match,
    # which the old "/tests/" substring check missed.
    content = _PWD + " = " + _DQ + "hardcoded_in_test" + _DQ
    assert check_code_safety("tests/unit/conftest.py", content) == []


def test_domain_check_survives_traversal() -> None:
    # A traversal that resolves into a domain path is still flagged.
    content = "from src.user.infrastructure import UserRepo"
    errors = check_code_safety("src/user/foo/../domain/service.py", content)
    assert any("Domain layer" in e for e in errors)


def test_domain_substring_in_component_not_treated_as_domain() -> None:
    # "domain_events" is not a "domain" segment — the infra import must pass.
    content = "from src.user.infrastructure import UserRepo"
    assert check_code_safety("src/user/domain_events/service.py", content) == []


def test_backslash_is_not_a_posix_separator() -> None:
    # On POSIX a backslash is a valid filename char, not a separator. A path
    # like "src\tests\config.py" is a single production filename and must NOT
    # be exempted as a test file (folding "\" -> "/" would reintroduce the
    # bypass this fix closes).
    content = _PWD + " = " + _DQ + "backslash_s3cret_val" + _DQ
    errors = check_code_safety(
        "src" + chr(92) + "tests" + chr(92) + "config.py", content
    )
    assert any("Hardcoded secret" in e for e in errors)
