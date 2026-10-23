"""目标连接工厂（第一批批1-2b）：PG 入 app + Oracle 方言实现。

- PgTargetConnection：从隔离验收测试晋升为应用实现（SQLAlchemy 引擎，
  FOR UPDATE + lock_timeout + SELECT now() 目标时钟；真实事务语义）；
- OracleTargetConnection：oracledb 直连（连接工厂注入，凭据由容器侧
  解析，本模块不落明文）。Oracle DATE/TIMESTAMP 绑定统一转院区时区
  naive 墙钟（不经字符串、不经 UTC 平移）；行锁用 FOR UPDATE WAIT n；
  SYSTEM_TIME 取 SYSTIMESTAMP 并换算院区时区（目标库时钟为唯一来源）。

边界声明：Oracle 方言在本机无隔离环境，集成验证如实 NOT_RUN；
不以 SQLite/PG 冒充 Oracle 事务证明。
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline.target_executor import AmbiguousCommit

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")


class TargetFactoryError(ContractViolation):
    """目标连接装配失败。"""


def _wall_clock(moment: datetime) -> datetime:
    if moment is not None and moment.tzinfo is not None:
        return moment.astimezone(BUSINESS_TZ).replace(tzinfo=None)
    return moment


def _pg_quote_ident(name: str) -> str:
    if not name or any(c in name for c in '";'):
        raise TargetFactoryError(f"非法标识符: {name!r}")
    return f'"{name}"'


class PgTargetConnection:
    """TargetConnection 协议的 PostgreSQL 实现（生产/隔离验收同源）。

    fault_injection 仅供隔离验收复现 COMMIT_UNKNOWN（真实路径默认关闭）。
    """

    def __init__(
        self,
        engine,
        *,
        lock_timeout_seconds: int = 10,
        fault_injection: Mapping[str, bool] | None = None,
        on_fault_fired: Callable[[], None] | None = None,
    ) -> None:
        self._engine = engine
        self._conn = engine.connect()
        self._tx = None
        self._lock_timeout = lock_timeout_seconds
        self._fault = dict(fault_injection or {})
        self._commit_answer_lost_armed = bool(
            self._fault.get("commit_answer_lost_once")
        )
        self._on_fault_fired = on_fault_fired
        self._wrote = False

    # -- 协议实现 -------------------------------------------------------

    def begin(self) -> None:
        from sqlalchemy import text

        self._tx = self._conn.begin()
        self._conn.execute(
            text(f"SET LOCAL lock_timeout = '{self._lock_timeout}s'")
        )

    def lock_and_read_rows(self, table, key_columns, keys):
        if not keys:
            return {}
        from sqlalchemy import text

        cols = ", ".join(_pg_quote_ident(c) for c in key_columns)
        flat = [k[0] if len(key_columns) == 1 else k for k in keys]
        rows = self._conn.execute(
            text(
                f"SELECT * FROM {table} WHERE ({cols}) = ANY(:keys) FOR UPDATE"
            ),
            {"keys": flat if len(key_columns) == 1 else [list(k) for k in keys]},
        ).mappings().all()
        return {tuple(r[c] for c in key_columns): dict(r) for r in rows}

    def delete_rows(self, table, key_columns, keys) -> int:
        if not keys:
            return 0
        from sqlalchemy import text

        self._wrote = True
        cols = ", ".join(_pg_quote_ident(c) for c in key_columns)
        flat = [k[0] if len(key_columns) == 1 else k for k in keys]
        result = self._conn.execute(
            text(f"DELETE FROM {table} WHERE ({cols}) = ANY(:keys)"),
            {"keys": flat if len(key_columns) == 1 else [list(k) for k in keys]},
        )
        return result.rowcount

    def current_timestamp(self) -> datetime:
        from sqlalchemy import text

        value = self._conn.execute(text("SELECT now()")).scalar()
        if value is not None and value.tzinfo is None:
            from datetime import timezone as _tz

            value = value.replace(tzinfo=_tz.utc)
        return value

    def insert_rows(self, table, columns, rows) -> int:
        if not rows:
            return 0
        from sqlalchemy import text

        self._wrote = True
        collist = ", ".join(_pg_quote_ident(c) for c in columns)
        ph = ", ".join(f":{c}" for c in columns)
        result = self._conn.execute(
            text(f"INSERT INTO {table} ({collist}) VALUES ({ph})"),
            [self._bind_row(dict(r)) for r in rows],
        )
        return result.rowcount

    def update_rows(self, table, columns, rows, *, key_columns) -> int:
        if not rows:
            return 0
        from sqlalchemy import text

        self._wrote = True
        setlist = ", ".join(
            f"{_pg_quote_ident(c)} = :{c}" for c in columns if c not in key_columns
        )
        where = " AND ".join(f"{_pg_quote_ident(c)} = :{c}" for c in key_columns)
        result = self._conn.execute(
            text(f"UPDATE {table} SET {setlist} WHERE {where}"),
            [self._bind_row(dict(r)) for r in rows],
        )
        return result.rowcount

    def find_receipt(self, receipt_table, operation_id):
        from sqlalchemy import text

        row = self._conn.execute(
            text(f"SELECT * FROM {receipt_table} WHERE operation_id = :oid"),
            {"oid": operation_id},
        ).mappings().first()
        return dict(row) if row else None

    def insert_receipt(self, receipt_table, receipt) -> None:
        from sqlalchemy import text

        cols = list(receipt.keys())
        collist = ", ".join(_pg_quote_ident(c) for c in cols)
        ph = ", ".join(f":{c}" for c in cols)
        self._conn.execute(
            text(f"INSERT INTO {receipt_table} ({collist}) VALUES ({ph})"),
            self._bind_row(dict(receipt)),
        )

    def commit(self) -> bool:
        if self._commit_answer_lost_armed and self._wrote:
            # 确定性 ground truth：实际回滚（隔离验收专用；真实"结果未知"
            # 由裁定流程查回执表确认）。只在发生过写的事务提交时触发，且
            # 触发即全局解除（on_fault_fired）——只读/预览连接不消耗注入。
            self._commit_answer_lost_armed = False
            if self._on_fault_fired is not None:
                self._on_fault_fired()
            try:
                self._tx.rollback()
            finally:
                self._close_quietly()
            raise AmbiguousCommit("提交应答丢失（隔离验收注入）")
        try:
            self._tx.commit()
            return True
        except Exception:
            return False
        finally:
            self._close_quietly()

    def rollback(self) -> None:
        try:
            if self._tx is not None:
                self._tx.rollback()
        finally:
            self._close_quietly()

    def close(self) -> None:
        self._close_quietly()

    # -- 内部 -----------------------------------------------------------

    def _bind_row(self, row: Mapping) -> dict:
        return {k: _wall_clock(v) if isinstance(v, datetime) else v for k, v in row.items()}

    def _close_quietly(self) -> None:
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001 - 关闭失败不掩盖主结果
            pass
        self._tx = None


class OracleTargetConnection:
    """TargetConnection 协议的 Oracle 实现（oracledb，方言级待隔离验证）。

    - 连接由注入工厂提供（容器内解析长期凭据；本模块零明文）；
    - 绑定统一院区时区 naive 墙钟；SYSTEM_TIME=SYSTIMESTAMP 换算院区时区；
    - 行锁 FOR UPDATE WAIT n（lock_timeout 秒）；IN 列表分块（≤500/块）；
    - commit 网络类异常 → AmbiguousCommit（结果不明）；其余回滚 → False。
    """

    CHUNK = 500

    def __init__(
        self,
        connection_factory: Callable[[], object],
        *,
        lock_wait_seconds: int = 10,
    ) -> None:
        self._connection_factory = connection_factory
        self._lock_wait = lock_wait_seconds
        self._conn = None

    def _connection(self):
        if self._conn is None:
            self._conn = self._connection_factory()
        return self._conn

    @staticmethod
    def _ident(name: str) -> str:
        if not name or any(c in name for c in ';"'):
            raise TargetFactoryError(f"非法标识符: {name!r}")
        return name

    def _chunks(self, keys: Sequence[tuple]) -> list[list[tuple]]:
        return [
            list(keys[i : i + self.CHUNK])
            for i in range(0, len(keys), self.CHUNK)
        ]

    def _key_predicate(self, key_columns: Sequence[str], chunk: Sequence[tuple]) -> tuple[str, list[dict]]:
        """(k1=:k0c0 AND k2=:k0c1) OR (...) 谓词 + 命名绑定。"""
        clauses: list[str] = []
        binds: dict[str, object] = {}
        for row_index, key in enumerate(chunk):
            parts = []
            for col_index, column in enumerate(key_columns):
                name = f"k{row_index}_{col_index}"
                binds[name] = _wall_clock(key[col_index]) if isinstance(key[col_index], datetime) else key[col_index]
                parts.append(f"{self._ident(column)} = :{name}")
            clauses.append("(" + " AND ".join(parts) + ")")
        return " OR ".join(clauses), binds

    def begin(self) -> None:
        conn = self._connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        finally:
            cursor.close()

    def lock_and_read_rows(self, table, key_columns, keys):
        if not keys:
            return {}
        conn = self._connection()
        out: dict[tuple, Mapping] = {}
        table_name = self._ident(table)
        for chunk in self._chunks(keys):
            predicate, binds = self._key_predicate(key_columns, chunk)
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"SELECT * FROM {table_name} WHERE {predicate} "
                    f"FOR UPDATE WAIT {self._lock_wait}",
                    binds,
                )
                columns = [d[0].upper() for d in cursor.description]
                for raw in cursor.fetchall():
                    row = {
                        col: _wall_clock(value) if isinstance(value, datetime) else value
                        for col, value in zip(columns, raw)
                    }
                    key = tuple(row.get(c.upper()) for c in key_columns)
                    out[key] = row
            finally:
                cursor.close()
        return out

    def delete_rows(self, table, key_columns, keys) -> int:
        if not keys:
            return 0
        conn = self._connection()
        table_name = self._ident(table)
        deleted = 0
        for chunk in self._chunks(keys):
            predicate, binds = self._key_predicate(key_columns, chunk)
            cursor = conn.cursor()
            try:
                deleted += cursor.execute(
                    f"DELETE FROM {table_name} WHERE {predicate}", binds
                ).rowcount
            finally:
                cursor.close()
        return deleted

    def current_timestamp(self) -> datetime:
        conn = self._connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT SYSTIMESTAMP AT TIME ZONE 'Asia/Shanghai' FROM DUAL"
            )
            value = cursor.fetchone()[0]
        finally:
            cursor.close()
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=BUSINESS_TZ)
        return value

    def _dml_rows(self, rows: Sequence[Mapping], columns: Sequence[str]) -> list[dict]:
        out = []
        for row in rows:
            bound = {}
            for column in columns:
                value = row.get(column)
                bound[column.lower()] = (
                    _wall_clock(value) if isinstance(value, datetime) else value
                )
            out.append(bound)
        return out

    def insert_rows(self, table, columns, rows) -> int:
        if not rows:
            return 0
        conn = self._connection()
        table_name = self._ident(table)
        collist = ", ".join(self._ident(c) for c in columns)
        ph = ", ".join(f":{c.lower()}" for c in columns)
        cursor = conn.cursor()
        try:
            cursor.executemany(
                f"INSERT INTO {table_name} ({collist}) VALUES ({ph})",
                self._dml_rows(rows, columns),
            )
            return len(rows)
        finally:
            cursor.close()

    def update_rows(self, table, columns, rows, *, key_columns) -> int:
        if not rows:
            return 0
        conn = self._connection()
        table_name = self._ident(table)
        set_cols = [c for c in columns if c not in key_columns]
        setlist = ", ".join(f"{self._ident(c)} = :{c.lower()}" for c in set_cols)
        where = " AND ".join(f"{self._ident(c)} = :{c.lower()}" for c in key_columns)
        cursor = conn.cursor()
        try:
            cursor.executemany(
                f"UPDATE {table_name} SET {setlist} WHERE {where}",
                self._dml_rows(rows, columns),
            )
            return len(rows)
        finally:
            cursor.close()

    def find_receipt(self, receipt_table, operation_id):
        conn = self._connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"SELECT * FROM {self._ident(receipt_table)} "
                "WHERE operation_id = :oid",
                {"oid": operation_id},
            )
            columns = [d[0].upper() for d in cursor.description]
            raw = cursor.fetchone()
        finally:
            cursor.close()
        if raw is None:
            return None
        return {
            col: (_wall_clock(v) if isinstance(v, datetime) else v)
            for col, v in zip(columns, raw)
        }

    def insert_receipt(self, receipt_table, receipt) -> None:
        conn = self._connection()
        cols = list(receipt.keys())
        collist = ", ".join(self._ident(c) for c in cols)
        ph = ", ".join(f":{c.lower()}" for c in cols)
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"INSERT INTO {self._ident(receipt_table)} ({collist}) VALUES ({ph})",
                self._bind_receipt(dict(receipt)),
            )
        finally:
            cursor.close()

    @staticmethod
    def _bind_receipt(receipt: Mapping) -> dict:
        return {
            k.lower(): (
                _wall_clock(v) if isinstance(v, datetime)
                else (v.isoformat() if isinstance(v, str) else v)
            )
            for k, v in receipt.items()
        }

    def commit(self) -> bool:
        try:
            self._connection().commit()
            return True
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            # 网络/中断类：提交结果不明（禁止盲判失败触发重放）
            if any(
                marker in message
                for marker in ("DPY-4011", "ORA-12541", "ORA-12547", "ORA-03113", "ORA-03114")
            ):
                raise AmbiguousCommit(f"Oracle 提交结果不明: {type(exc).__name__}") from exc
            return False
        finally:
            self._close_quietly()

    def rollback(self) -> None:
        try:
            if self._conn is not None:
                self._conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._close_quietly()

    def close(self) -> None:
        self._close_quietly()

    def _close_quietly(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass
            self._conn = None


def build_target_connection_factory(
    *,
    dialect: str,
    url_env: str | None = None,
    dsn: str | None = None,
    credential_ref: str | None = None,
    fault_injection: Mapping[str, bool] | None = None,
    lock_wait_seconds: int = 10,
) -> Callable[[], object]:
    """目标连接工厂：pg=SQLAlchemy 引擎（URL 取受控环境变量）；
    oracle=oracledb 工厂（凭据引用容器侧解析）。"""
    if dialect == "pg":
        import os

        from sqlalchemy import create_engine

        url = url_env and os.environ.get(url_env)
        if not url:
            raise TargetFactoryError(
                f"PG 目标需环境变量 {url_env}（未设置即拒绝）"
            )
        engine = create_engine(url)
        # 隔离验收故障注入：全局一次性——首次"写事务提交"触发后解除，
        # 后续连接/干净重放不再注入
        armed = {
            "commit_answer_lost_once": bool((fault_injection or {}).get("commit_answer_lost_once")),
        }

        def pg_factory() -> PgTargetConnection:
            def _fired() -> None:
                armed["commit_answer_lost_once"] = False

            return PgTargetConnection(
                engine,
                fault_injection=dict(armed),
                on_fault_fired=_fired,
                lock_timeout_seconds=lock_wait_seconds,
            )

        return pg_factory
    if dialect == "oracle":
        from app.services.reporting_pipeline.source_factory import (
            build_oracle_connection_factory,
        )

        if not dsn or not credential_ref:
            raise TargetFactoryError("Oracle 目标需 dsn + credential_ref")
        connection_factory = build_oracle_connection_factory(
            dsn=dsn, credential_ref=credential_ref
        )

        def oracle_factory() -> OracleTargetConnection:
            return OracleTargetConnection(
                connection_factory, lock_wait_seconds=lock_wait_seconds
            )

        return oracle_factory
    raise TargetFactoryError(f"不支持的目标方言: {dialect}")
