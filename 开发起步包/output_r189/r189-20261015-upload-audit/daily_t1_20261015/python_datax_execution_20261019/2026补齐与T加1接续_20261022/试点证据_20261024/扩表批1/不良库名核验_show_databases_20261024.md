# ③ 不良库名核验证据（2026-10-24）

- 通道：8.83 容器 `data-asset-api` 内 python（pymysql），凭据文件 `/etc/data-asset/credentials/adverse_event_mysql_10_10_10_50.readonly`（只进内存，未打印）
- 目标：10.10.10.50:3306，`SHOW DATABASES`（一条只读）
- 结果：`['information_schema', 'mas', 'mas_activiti', 'mds', 'mysql', 'performance_schema', 'pitaya_bi', 'pitaya_cmi', 'pitaya_gtt', 'pitaya_identity', 'pitaya_rule', 'qds']`
- **结论：`mas` 在列** → 按台账 `mas` 走，`扩表bindings_批1_20261024.json` 与冻结件无需修改，指纹 1f5a09ef… 维持有效
- 旁证：库列表另有 mas_activiti（工作流）与 pitaya_* 系列（病理 BI 系），均非不良事件业务库；不良视图对象=`mas.v_emr_adverse_event_final`（锚点 EFFECTIVE_TIME）
