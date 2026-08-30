# 审查_zcode（verify/round-2 独立初审 · 问题清单草案）

> GLM 作为 153 执行方的事后自审：换视角重读改动，列真实风险点（非走过场）。
> 每条=编号|位置|问题猜想|严重度|验证方法。

| # | 位置 | 问题猜想 | 严重度 | 验证方法 |
|---|---|---|---|---|
| Z1 | backend/app/services/db_connectors.py（execute_readonly 各分支 max_rows+1） | A4 改变连接器契约后，**无 SQL 级 ROWNUM/LIMIT 的调用方**（重点：metadata_collector.py 多处 `max_rows=10000`、identity_source_collector 的 staff/group 查询）会多取 1 行，突破"恰好 N 行"采集上限口径；执行报告仅核实了 quality_sql_runner 夹紧与 SQL 内建限制的调用方，metadata_collector 未逐处核实 | 中 | grep metadata_collector 的 execute_readonly 调用，核对每处 SQL 是否自带 ROWNUM/LIMIT；无者评估多 1 行的影响 |
| Z2 | backend/app/api/v1/ai.py（propose-sql/export-context/system-context 挂 ai.context.read） | 行为变化：**未绑定角色的 API Token**（unbound）此前可调 propose-sql/system-context/export-context（这些端点原无权限码、get_current_user 也未调用），现在 require_permission→get_current_user 403。若有外部自动化（Dify/MCP/调度脚本）用未绑定 token 调这些端点会断流 | 中 | 生产 8.83 查 asset_api_keys 未绑定但 recent last_used_at 的 key；或平台日志 grep 403；至少在核查报告标注为"已知行为变化需运维确认" |
| Z3 | backend/app/api/v1/queries.py（version_diff 掩码形态 current_sql=null） | 前端 query-center 是否消费 diff 端点并直接渲染 current_sql？无权限用户会看到空白而非提示 | 低 | grep frontend/src 对 `/diff` 的调用与渲染分支 |
| Z4 | backend/app/api/v1/quality.py（C5 dedup_index 预载） | 预载只取本轮 enabled 规则的 open/acknowledged findings；若库里存在**同 (rule_code,target_type,target_ref) 的多条 open 重复行**，原 db.scalar 取任意一条、新 setdefault 取第一条——语义等价但依赖查询顺序；且新增行回填索引后同批重复 target 去重靠索引（原靠 autoflush 后查询可见性）——理论上等价，建议抽查 | 低 | 测试库造两条同 target 的 open finding 跑 checks/run，断言不新增重复行且更新其一 |
| Z5 | backend/app/services/jhemr_identity_adapter.py（A6 隧道等待） | 10s 等待上限对慢网络/首次 SSH 握手可能不够（原为 0.5s 更差，属改进）；且 `socket.create_connection` 探测本地端口会消费掉 sshd 的连接 accept——对 `-N` 转发无影响，但需确认不会触发 PortForwarding 抖动 | 低 | 代码走查 + 观察 JHEMR 夜跑首日日志 |
| Z6 | backend/app/api/v1/permissions.py（dict_admin 默认矩阵补 3 码） | 生产生效依赖重跑 `POST /api/v1/permissions/seed`；若发布后忘跑，dict_admin 调 sync/retry/stop 端点 403（fail-closed 生效但误伤合法运维）。交接已写，需在核查报告置顶提醒 | 中 | 发布清单核对；生产 seed 后 GET /permissions/roles/dict_admin/matrix 验证 |
| Z7 | frontend/src/utils/http/index.ts（qs arrayFormat=repeat） | 全局序列化器变更：若存在**未 grep 到的数组 query 参数**（如动态构造 params 对象），原先 `a[0]=x` 后端收不到数组（本来就是坏），现在变 `a=x&a=y` 后端能收到——行为从"坏"变"对"，但若后端某端点把重复参数当非法会新报错。理论净改善，标注即可 | 低 | 全仓 grep `params: {` 附近数组字面量（已做一轮，仅 rule_codes）|
| Z8 | frontend/src/composables/usePagedList.ts + 6 试点页 | 分页状态从页面局部 ref 迁到 composable；dict/sync-diffs 原先 `params` reactive 含 page/page_size，改造后模板绑 composable 引用——若某处仍引用 `params.page`（漏改）typecheck 已兜底为 0 错，但**运行时 v-model 绑定到 composable 的 ref 解包**（模板自动解包顶层 ref，但 composable 返回的 ref 在 setup 顶层解包后 v-model 正常）——已过 166 测试；风险集中在无测试覆盖的交互（重置筛选后页码、pageSize 切换） | 低 | 人工点验 6 页分页/搜索/重置交互 |
| Z9 | backend/app/api/v1/ai.py + dict_medical_api.py（B5 权限收窄） | test_write_route_auth_scan 只扫"公开白名单"，不校验权限码级别；新矩阵测试锁定装饰器存在，但**运行时角色判定**（require_permission 实际查询 RBAC）只有 conftest 的 platform_admin 路径被测——quality_admin/dict_admin/ai_user 真实 403/200 矩阵未端到端断言（部分在 security_audit 纯逻辑测试） | 中 | 测试库跑一次 seed 后用三个角色 token 实测新码端点 200/403 |
| Z10 | backend/app/api/v1/graph.py（C1 _EndpointResolver） | resolve_exact 对 `schema_name is None` 的匹配：原 resolve_endpoint 用 `AssetTable.schema_name.is_(None)`（SQL NULL 语义），新内存版 `e[1] is None` 等价；但**空串 schema**：SQL `== ""` vs 内存 `== ""` 等价 ✓。`namespace_name` 空串 vs NULL 的 or_ 条件等价 ✓。主要残余风险：行 tuple 顺序/None 规整在 PG 返回下无差异 | 低 | test_graph 既有 33 测试 + 新 2 锁定已覆盖；抽查跨系统同名表用例 |
| Z11 | frontend E 批 49 处 `ElMessage.error(extractErrorDetail(...))` 机械替换 | 个别替换点原 fallback 文案被统一化（如"导出失败"保留、其他变文案合并），且 catch 内若还有后续逻辑（重置状态）未受影响；风险=极低，但**替换脚本对跨行/变量名变体（e/E/err/error）只覆盖单行形态**，残余内联形态仍在（71→49 替换，余 22 处未收敛，属计划内"仅收敛既有重复"范围） | 低 | grep 残余 `response?.data?.detail` 计数（22 处）确认无功能问题 |
| Z12 | backend D2 get_request_operator 17 处替换 | relation_reviews 三处默认 "reviewer"、其余 "system"；原样板 `except Exception: pass` 捕一切，新 helper 只捕 HTTPException——若 get_current_user 未来抛非 HTTP 异常会冒泡（当前不会）；等价性依赖 conftest platform_admin 测试 | 低 | 代码走查（已做）+ audit_log 断言 operator 值的既有测试 |
| Z13 | 环境面 | 当日两会话互踩已恢复；但 **8.83 测试库 schema 曾整体重建**，序列/数据与重建前不可比（若有人拿旧数据比对）；最终门禁数字（1152/0）来自重建后的干净库，可信 | 信息 | 无需动作，报告记录 |

## 自审结论

无"高危阻断"级自认问题；中等级 4 条（Z1/Z2/Z6/Z9）集中在**行为变化的调用方影响**与**生产 seed 依赖**，均可命令验证或运维确认。建议外部审查重点：A4 连接器契约外溢面、B5 权限矩阵运行时、C1/C3/C4 不变性、前端六页交互回归。
