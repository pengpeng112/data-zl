"""Runtime MySQL connector honors per-source ssl_disabled and nothing else."""
from __future__ import annotations

import sys
from types import SimpleNamespace

from app.services.db_connectors import MysqlConnector, transport_kwargs


class _Cursor:
    def execute(self, *_args, **_kwargs):
        return None

    def close(self):
        return None


class _Connection:
    def cursor(self):
        return _Cursor()

    def ping(self):
        return None

    def close(self):
        return None


def test_transport_kwargs_is_mysql_opt_in_only():
    assert transport_kwargs("mysql", None) == {}
    assert transport_kwargs("mysql", {}) == {}
    assert transport_kwargs("mysql", {"ssl_disabled": False}) == {}
    assert transport_kwargs("mysql", {"ssl_disabled": "true"}) == {}
    assert transport_kwargs("oracle", {"ssl_disabled": True}) == {}
    assert transport_kwargs("mysql", {"ssl_disabled": True, "write_username_masked": "a***"}) == {
        "ssl_disabled": True,
    }


def test_mysql_connect_passes_ssl_disabled_only_when_opted_in(monkeypatch):
    calls = []

    def connect(**kwargs):
        calls.append(kwargs)
        return _Connection()

    monkeypatch.setitem(
        sys.modules,
        "pymysql",
        SimpleNamespace(connect=connect, cursors=SimpleNamespace(DictCursor=dict)),
    )
    plain = MysqlConnector(host="10.10.8.135", port=3306, database="core2db", user="u", password="p")
    plain.connect()
    assert "ssl_disabled" not in calls[0]

    opted = MysqlConnector(
        host="10.10.8.135", port=3306, database="core2db", user="u", password="p", ssl_disabled=True,
    )
    opted.connect()
    assert calls[1]["ssl_disabled"] is True
    assert calls[1]["password"] == "p"


