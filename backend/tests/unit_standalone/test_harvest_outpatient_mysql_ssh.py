from __future__ import annotations

import importlib.util
import shlex
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "harvest_outpatient_mysql_ssh.py"
SPEC = importlib.util.spec_from_file_location("harvest_outpatient_mysql_ssh", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_mysql_command_keeps_password_out_of_shell() -> None:
    sql = "SELECT 'x; rm -f /tmp/should-not-run' value"
    command = MODULE._mysql_command(
        "/tmp/data asset.cnf",
        sql,
    )

    assert "--defaults-extra-file='/tmp/data asset.cnf'" in command
    assert "MYSQL_PWD" not in command
    assert "password" not in command.lower()
    assert shlex.split(command)[-1] == sql


def test_mysql_option_value_escapes_shell_like_characters() -> None:
    value = MODULE._mysql_option_value('a$(`b`)"\\c')

    assert value == '"a$(`b`)\\"\\\\c"'


@pytest.mark.parametrize("value", ["line1\nline2", "line1\rline2", "a\x00b"])
def test_mysql_option_value_rejects_control_characters(value: str) -> None:
    with pytest.raises(ValueError):
        MODULE._mysql_option_value(value)


def test_sql_literal_escapes_quote() -> None:
    assert MODULE._sql_literal("db'name") == "'db''name'"


def test_script_fails_closed_on_host_keys_and_avoids_password_env_shell() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "paramiko.RejectPolicy()" in source
    assert "AutoAddPolicy" not in source
    assert "MYSQL_PWD" not in source
    assert 'target.exec_command(f"export' not in source
    assert source.index("sftp.chmod(option_file, 0o600)") < source.index(
        'fh.write("\\n".join(option_lines) + "\\n")'
    )
