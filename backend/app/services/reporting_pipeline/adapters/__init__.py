"""R189-T1 读取/执行适配器：Python 路线与 DataX 路线共用 manifest 语义。

引擎路由固定（每表 engine 不因失败换工具）；无授权不得 fallback：
- 护理原整视图 DataX-only 线索与 B04 患者键 Python 通道是两条独立路线；
- DataX 目标只允许白名单暂存对象，正式表由受控装载（E05）处理；
- 官方 OracleWriter 仅 INSERT（无 writeMode=update），querySql 必须带投影
  与范围。
"""

from app.services.reporting_pipeline.adapters.python_reader import (
    CancellationToken,
    OperationCancelled,
    PythonReaderAdapter,
    ReadBudget,
    ReadPage,
    RowSource,
    SourceCircuitBreaker,
    SourceError,
    classify_source_error,
)

__all__ = [
    "CancellationToken",
    "OperationCancelled",
    "PythonReaderAdapter",
    "ReadBudget",
    "ReadPage",
    "RowSource",
    "SourceCircuitBreaker",
    "SourceError",
    "classify_source_error",
]
